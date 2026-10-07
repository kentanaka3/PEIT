"""
Cryptographic core, session state machine, and device authorization registry
for the Personal Economic Inflation Tracker (PEIT) LAN security handshake.

Implements zero-cloud, privacy-preserving LAN authentication with:
- Ephemeral 6-digit PIN pairing sessions with bounded TTL.
- PBKDF2-HMAC-SHA256 key derivation and HMAC-SHA256 challenge-response proofs.
- Secure device bearer tokens and atomic JSON device authorization registry.
- Replay attack mitigation with fresh timestamp window (±60s) and bounded nonce tracking.
- Self-signed TLS X.509 certificate and key generation for local HTTPS transport.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import tempfile
import time
from typing import Any
from urllib.parse import urlencode

logger = logging.getLogger("peit.auth")

DEFAULT_PAIRING_TTL_SECONDS = 300  # 5 minutes
MAX_FAILED_PAIR_ATTEMPTS = 3
MAX_TIMESTAMP_DRIFT_SECONDS = 60.0  # ±60 seconds
NONCE_CACHE_MAX_SIZE = 10000
NONCE_TTL_SECONDS = 120.0  # Keep nonces slightly longer than timestamp drift window


def generate_ephemeral_pin() -> str:
  """Generate a cryptographically secure 6-digit numeric PIN formatted as '%06d'."""
  return f"{secrets.randbelow(1_000_000):06d}"


def generate_pairing_salt() -> str:
  """Generate a 16-byte cryptographically secure hexadecimal salt string."""
  return secrets.token_hex(16)


def generate_bearer_token() -> str:
  """Generate a 32-byte cryptographically secure URL-safe bearer token string."""
  return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
  """Calculate SHA-256 digest of a bearer token string."""
  return hashlib.sha256(token.encode("utf-8")).hexdigest()


def derive_pairing_key(pin: str, salt: str, iterations: int = 10000) -> bytes:
  """Derive a 256-bit symmetric key from PIN and salt using PBKDF2-HMAC-SHA256."""
  return hashlib.pbkdf2_hmac(
      "sha256",
      pin.encode("utf-8"),
      salt.encode("utf-8"),
      iterations=iterations,
      dklen=32,
  )


def compute_pin_proof(derived_key: bytes, session_id: str, device_id: str) -> str:
  """Calculate HMAC-SHA256 proof over session_id + device_id using derived key."""
  message = f"{session_id}{device_id}".encode("utf-8")
  return hmac.new(derived_key, message, hashlib.sha256).hexdigest()


def verify_pin_proof(
    derived_key: bytes,
    session_id: str,
    device_id: str,
    candidate_proof: str,
) -> bool:
  """Verify PIN challenge-response proof using constant-time comparison."""
  expected_proof = compute_pin_proof(derived_key, session_id, device_id)
  return hmac.compare_digest(expected_proof, candidate_proof)


def compute_request_signature(
    token_or_key: str | bytes,
    method: str,
    path: str,
    timestamp: str | float,
    nonce: str,
    body: bytes = b"",
) -> str:
  """Compute HMAC-SHA256 request signature over HTTP request metadata and body.

  Message format: METHOD\nPATH\nTIMESTAMP\nNONCE\nBODY_SHA256
  """
  key = token_or_key.encode("utf-8") if isinstance(token_or_key, str) else token_or_key
  body_hash = hashlib.sha256(body).hexdigest()
  message = f"{method.upper()}\n{path}\n{str(timestamp)}\n{nonce}\n{body_hash}".encode(
      "utf-8"
  )
  return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_request_signature(
    token_or_key: str | bytes,
    method: str,
    path: str,
    timestamp: str | float,
    nonce: str,
    candidate_signature: str,
    body: bytes = b"",
) -> bool:
  """Verify request signature using constant-time comparison."""
  expected_signature = compute_request_signature(
      token_or_key, method, path, timestamp, nonce, body
  )
  return hmac.compare_digest(expected_signature, candidate_signature)


class NonceTracker:
  """Bounded memory LRU cache and TTL-based tracker for request nonces."""

  def __init__(
      self,
      max_size: int = NONCE_CACHE_MAX_SIZE,
      ttl: float = NONCE_TTL_SECONDS,
  ) -> None:
    self.max_size = max_size
    self.ttl = ttl
    self._nonces: collections.OrderedDict[str, float] = collections.OrderedDict()

  def _prune(self, now: float) -> None:
    """Evict expired nonces and maintain bounded max size."""
    cutoff = now - self.ttl
    # Prune expired from oldest end
    while self._nonces:
      oldest_nonce, timestamp = next(iter(self._nonces.items()))
      if timestamp < cutoff:
        self._nonces.pop(oldest_nonce)
      else:
        break

    # If still larger than max size, evict oldest
    while len(self._nonces) > self.max_size:
      self._nonces.popitem(last=False)

  def check_and_add(self, nonce: str, now: float | None = None) -> bool:
    """Check if nonce has been seen. If unseen, record it and return True.

    Returns:
      True if the nonce is fresh and was successfully recorded.
      False if the nonce has already been observed (replay detected).
    """
    if not nonce:
      return False
    current_time = time.time() if now is None else now
    self._prune(current_time)

    if nonce in self._nonces:
      return False

    self._nonces[nonce] = current_time
    return True

  def __len__(self) -> int:
    return len(self._nonces)


def validate_timestamp_freshness(
    req_timestamp: float | str,
    now: float | None = None,
    max_drift: float = MAX_TIMESTAMP_DRIFT_SECONDS,
) -> bool:
  """Verify that request timestamp is within allowed drift window (±60 seconds)."""
  try:
    ts = float(req_timestamp)
  except (ValueError, TypeError):
    return False

  current_time = time.time() if now is None else now
  return abs(current_time - ts) <= max_drift


@dataclasses.dataclass
class PairedDevice:
  """Data model representing an authorized paired edge device."""

  device_id: str
  device_name: str
  token_hash: str
  paired_at: str
  last_seen_at: str

  def to_dict(self) -> dict[str, Any]:
    return dataclasses.asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PairedDevice:
    return cls(
        device_id=str(data["device_id"]),
        device_name=str(data.get("device_name", "")),
        token_hash=str(data["token_hash"]),
        paired_at=str(data.get("paired_at", "")),
        last_seen_at=str(data.get("last_seen_at", "")),
    )


class DeviceRegistry:
  """Persistent JSON registry for authorized paired mobile devices."""

  def __init__(self, registry_path: str | Path) -> None:
    self.path = Path(registry_path).resolve()
    self._devices: dict[str, PairedDevice] = {}
    self._load()

  def _load(self) -> None:
    """Load registry file from disk if present."""
    if not self.path.exists():
      self._devices = {}
      return

    try:
      with open(self.path, "r", encoding="utf-8") as f:
        data = json.load(f)
      devices_raw = data.get("devices", {})
      self._devices = {
          k: PairedDevice.from_dict(v) for k, v in devices_raw.items()
      }
    except Exception as exc:
      logger.warning("Could not read device registry from %s: %s", self.path, exc)
      self._devices = {}

  def _save(self) -> None:
    """Persist registry to disk atomically via temporary file and os.replace."""
    self.path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = self.path.parent
    serialized = {
        "version": "1.0",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "devices": {k: v.to_dict() for k, v in self._devices.items()},
    }
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=temp_dir,
        delete=False,
        prefix=".peit_devices_",
        suffix=".tmp",
    )
    temp_path = Path(temp_file.name)
    try:
      json.dump(serialized, temp_file, indent=2, ensure_ascii=False)
      temp_file.flush()
      os.fsync(temp_file.fileno())
      temp_file.close()
      os.replace(temp_path, self.path)
    except Exception:
      if temp_path.exists():
        temp_path.unlink(missing_ok=True)
      raise

  def register_device(
      self,
      device_id: str,
      device_name: str,
      bearer_token: str,
  ) -> PairedDevice:
    """Register or update an authorized device with a new bearer token."""
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    token_h = hash_token(bearer_token)
    device = PairedDevice(
        device_id=device_id,
        device_name=device_name,
        token_hash=token_h,
        paired_at=now_iso,
        last_seen_at=now_iso,
    )
    self._devices[device_id] = device
    self._save()
    logger.info("Device '%s' (%s) registered successfully", device_name, device_id)
    return device

  def validate_token(self, device_id: str, token: str) -> bool:
    """Validate bearer token against stored SHA-256 hash.

    Updates last_seen_at timestamp on successful validation.
    """
    device = self._devices.get(device_id)
    if not device:
      return False

    candidate_hash = hash_token(token)
    if hmac.compare_digest(device.token_hash, candidate_hash):
      device.last_seen_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
      try:
        self._save()
      except Exception as exc:
        logger.warning("Failed to update last_seen_at for %s: %s", device_id, exc)
      return True
    return False

  def is_device_known(self, device_id: str) -> bool:
    """Check if device_id exists in registry."""
    return device_id in self._devices

  def revoke_device(self, device_id: str) -> bool:
    """Revoke authorization for a device. Returns True if device was found and removed."""
    if device_id in self._devices:
      removed = self._devices.pop(device_id)
      self._save()
      logger.info(
          "Device '%s' (%s) revoked successfully", removed.device_name, device_id
      )
      return True
    return False

  def get_device(self, device_id: str) -> PairedDevice | None:
    """Retrieve PairedDevice by id."""
    return self._devices.get(device_id)

  def list_devices(self) -> list[PairedDevice]:
    """Return list of all registered PairedDevice instances."""
    return list(self._devices.values())


@dataclasses.dataclass
class PairingSession:
  """Ephemeral in-memory pairing session."""

  session_id: str
  pin: str
  salt: str
  derived_key: bytes
  expires_at: float
  failed_attempts: int = 0

  @property
  def is_expired(self) -> bool:
    return time.time() > self.expires_at


class PairingManager:
  """State machine governing local pairing sessions."""

  def __init__(self, ttl: int = DEFAULT_PAIRING_TTL_SECONDS) -> None:
    self.default_ttl = ttl
    self.active_session: PairingSession | None = None

  @property
  def is_pairing_active(self) -> bool:
    """Return True if an active pairing session exists and has not expired."""
    if self.active_session is None:
      return False
    return not self.active_session.is_expired

  def initiate_pairing(
      self,
      ttl: int | None = None,
      host: str = "127.0.0.1",
      port: int = 8000,
  ) -> dict[str, Any]:
    """Initiate a fresh pairing session with new ephemeral PIN and salt.

    Cancels any previous active session.
    """
    effective_ttl = ttl if ttl is not None else self.default_ttl
    session_id = secrets.token_hex(12)
    pin = generate_ephemeral_pin()
    salt = generate_pairing_salt()
    derived_key = derive_pairing_key(pin, salt)
    expires_at = time.time() + effective_ttl

    self.active_session = PairingSession(
        session_id=session_id,
        pin=pin,
        salt=salt,
        derived_key=derived_key,
        expires_at=expires_at,
        failed_attempts=0,
    )

    qr_params = urlencode(
        {"host": host, "port": str(port), "session": session_id, "salt": salt}
    )
    pairing_uri = f"peit://pair?{qr_params}"

    return {
        "session_id": session_id,
        "pin": pin,
        "salt": salt,
        "pairing_uri": pairing_uri,
        "expires_at": expires_at,
        "ttl": effective_ttl,
    }

  def confirm_pairing(
      self,
      session_id: str,
      device_id: str,
      pin_proof: str,
  ) -> tuple[bool, str]:
    """Verify proof of PIN possession for the active session.

    Returns:
      (True, "ok") on success.
      (False, error_reason) on failure.
    """
    session = self.active_session
    if session is None:
      return False, "invalid_or_missing_session"

    if session.is_expired:
      self.active_session = None
      return False, "session_expired"

    if session.session_id != session_id:
      return False, "invalid_or_missing_session"

    if session.failed_attempts >= MAX_FAILED_PAIR_ATTEMPTS:
      self.active_session = None
      return False, "too_many_attempts"

    is_valid = verify_pin_proof(
        session.derived_key, session_id, device_id, pin_proof
    )
    if not is_valid:
      session.failed_attempts += 1
      if session.failed_attempts >= MAX_FAILED_PAIR_ATTEMPTS:
        self.active_session = None
        return False, "too_many_attempts"
      return False, "invalid_pin_proof"

    # Success: Invalidate ephemeral session after single successful pairing
    self.active_session = None
    return True, "ok"

  def cancel_pairing(self) -> None:
    """Explicitly cancel active pairing session."""
    self.active_session = None


def generate_self_signed_cert(
    cert_path: str | Path,
    key_path: str | Path,
    host: str = "localhost",
    days: int = 365,
) -> str:
  """Generate a self-signed TLS X.509 certificate and private key.

  Uses system OpenSSL binary if present, or creates standard self-signed certificate.
  Returns SHA-256 fingerprint string formatted as colon-separated hex uppercase.
  """
  c_path = Path(cert_path).resolve()
  k_path = Path(key_path).resolve()
  c_path.parent.mkdir(parents=True, exist_ok=True)
  k_path.parent.mkdir(parents=True, exist_ok=True)

  openssl_cmd = shutil.which("openssl")
  if openssl_cmd:
    cmd = [
        openssl_cmd,
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(k_path),
        "-out",
        str(c_path),
        "-days",
        str(days),
        "-nodes",
        "-subj",
        f"/CN={host}/O=PEIT/OU=Local Sync",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
      raise RuntimeError(
          f"OpenSSL failed to generate certificate: {result.stderr}"
      )
  else:
    raise RuntimeError(
        "OpenSSL CLI is required to generate self-signed TLS certificates."
    )

  # Restrict private key permissions
  try:
    os.chmod(k_path, 0o600)
  except OSError:
    pass

  # Compute SHA-256 fingerprint of DER certificate
  der_bytes = ssl.PEM_cert_to_DER_cert(c_path.read_text(encoding="utf-8"))
  digest = hashlib.sha256(der_bytes).hexdigest().upper()
  fingerprint = ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))
  return fingerprint


def get_cert_fingerprint(cert_path: str | Path) -> str:
  """Read PEM certificate and return its SHA-256 fingerprint."""
  c_path = Path(cert_path).resolve()
  pem_text = c_path.read_text(encoding="utf-8")
  der_bytes = ssl.PEM_cert_to_DER_cert(pem_text)
  digest = hashlib.sha256(der_bytes).hexdigest().upper()
  return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))
