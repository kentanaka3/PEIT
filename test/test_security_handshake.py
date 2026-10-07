"""
Comprehensive security and handshake test suite for PEIT (Suite 12).

Tests the LAN Pairing Security Handshake and Authorization subsystem:
- PIN generation, TTL expiration, and rate-limited brute-force lockout (max attempts)
- PBKDF2-HMAC-SHA256 key derivation and HMAC-SHA256 challenge-response proofs
- Device authorization registry: registration, token validation, revoking, atomic persistence
- Freshness timestamp window and nonce replay attack rejection
- POST /api/v1/pair/initiate and POST /api/v1/pair/confirm (happy path and failure cases)
- POST /api/v1/sync/push security enforcement:
  * 200 OK with valid bearer token and fresh nonce/timestamp
  * 401 Unauthorized with missing or invalid token
  * 403 Forbidden with revoked/unknown device
  * 400 Bad Request with replayed nonce or expired timestamp
  * --insecure-lan backward compatibility
- Self-signed TLS certificate generation and SHA-256 fingerprint verification
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from peit.auth import (
    DEFAULT_PAIRING_TTL_SECONDS,
    MAX_FAILED_PAIR_ATTEMPTS,
    DeviceRegistry,
    NonceTracker,
    PairingManager,
    compute_pin_proof,
    compute_request_signature,
    derive_pairing_key,
    generate_bearer_token,
    generate_ephemeral_pin,
    generate_pairing_salt,
    generate_self_signed_cert,
    get_cert_fingerprint,
    hash_token,
    validate_timestamp_freshness,
    verify_pin_proof,
    verify_request_signature,
)
from peit.cli import build_parser, main
from peit.server import create_server


def make_request(
    base_url: str,
    path: str,
    method: str = "GET",
    data: dict[str, Any] | list[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any, dict[str, str]]:
  """Helper to make HTTP requests against the test server using urllib."""
  req_headers = {"Accept": "application/json"}
  if headers:
    req_headers.update(headers)

  body_bytes = None
  if data is not None:
    body_bytes = json.dumps(data).encode("utf-8")
    req_headers["Content-Type"] = "application/json"
  elif method in ("POST", "PUT"):
    body_bytes = b""
    req_headers["Content-Length"] = "0"

  req = urllib.request.Request(
      f"{base_url}{path}",
      data=body_bytes,
      headers=req_headers,
      method=method,
  )

  try:
    with urllib.request.urlopen(req) as resp:
      status = resp.status
      resp_headers = dict(resp.headers)
      raw = resp.read().decode("utf-8")
      try:
        parsed_body = json.loads(raw)
      except Exception:
        parsed_body = raw
      return status, parsed_body, resp_headers
  except urllib.error.HTTPError as err:
    status = err.code
    resp_headers = dict(err.headers)
    raw = err.read().decode("utf-8")
    try:
      parsed_body = json.loads(raw)
    except Exception:
      parsed_body = raw
    return status, parsed_body, resp_headers


def sample_receipt_entry(
    receipt_id: str = "rec-sec-001",
    item: str = "espresso 250ml",
    paid_total: float = -3.50,
) -> dict[str, Any]:
  """Generate a minimal valid 25-column receipt entry for sync testing."""
  return {
      "receipt_id": receipt_id,
      "receipt_date": "2026-03-10",
      "merchant": "Cafe Rosetta",
      "item": item,
      "brand": "In-house",
      "category": "Food and beverages",
      "quantity": 1.0,
      "pack_size": 1.0,
      "unit": "cup",
      "unit_price": abs(paid_total),
      "currency": "MXN",
      "discount": 0.0,
      "fee": 0.0,
      "tax": 0.0,
      "deposit": 0.0,
      "paid_total": paid_total,
      "event_type": "recurring",
      "store_tier": "A",
      "store_rating": 4.9,
      "brand_tier": "A",
      "brand_rating": 4.8,
      "product_tier": "A",
      "product_rating": 5.0,
      "availability": "in_stock",
      "notes": "Testing secure push",
      "account": "default:checking",
  }


@pytest.fixture
def secure_server(tmp_path: Path):
  """Spins up a test server in secure mode with isolated ledger and device registry."""
  ledger_path = tmp_path / "secure_ledger.jsonl"
  registry_path = tmp_path / "test_devices.json"
  server = create_server(
      ledger_path,
      host="127.0.0.1",
      port=0,
      secure=True,
      device_registry_path=registry_path,
  )
  port = server.server_address[1]
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()

  base_url = f"http://127.0.0.1:{port}"
  yield server, base_url, ledger_path, registry_path

  server.shutdown()
  server.server_close()
  thread.join(timeout=3.0)


# ============================================================================
# 1. Cryptographic Primitives & Derivations
# ============================================================================


def test_t12_1_ephemeral_pin_and_salt_generation():
  """T12.1: Ephemeral 6-digit PIN and 16-byte salt generation format."""
  pins = {generate_ephemeral_pin() for _ in range(50)}
  assert len(pins) > 40  # high entropy
  for pin in pins:
    assert len(pin) == 6
    assert pin.isdigit()

  salt1 = generate_pairing_salt()
  salt2 = generate_pairing_salt()
  assert len(salt1) == 32  # 16 bytes in hex = 32 chars
  assert salt1 != salt2


def test_t12_2_pbkdf2_key_derivation_and_hmac_proof():
  """T12.2: PBKDF2-HMAC-SHA256 key derivation and HMAC-SHA256 challenge-response."""
  pin = "123456"
  salt = "a" * 32
  session_id = "sess_001"
  device_id = "phone_abc"

  key1 = derive_pairing_key(pin, salt, iterations=1000)
  key2 = derive_pairing_key(pin, salt, iterations=1000)
  assert key1 == key2
  assert len(key1) == 32

  proof = compute_pin_proof(key1, session_id, device_id)
  assert isinstance(proof, str)
  assert len(proof) == 64  # SHA-256 hex string

  # Verify proof matches
  assert verify_pin_proof(key1, session_id, device_id, proof) is True

  # Verify incorrect PIN or device fails
  wrong_key = derive_pairing_key("654321", salt, iterations=1000)
  assert verify_pin_proof(wrong_key, session_id, device_id, proof) is False
  assert verify_pin_proof(key1, session_id, "wrong_device", proof) is False
  assert verify_pin_proof(key1, "wrong_session", device_id, proof) is False


def test_t12_3_request_signature_and_verification():
  """T12.3: Request signing and constant-time HMAC verification."""
  token = generate_bearer_token()
  method = "POST"
  path = "/api/v1/sync/push"
  now_ts = time.time()
  nonce = "nonce_123"
  body = b'{"entries": []}'

  sig = compute_request_signature(token, method, path, now_ts, nonce, body)
  assert verify_request_signature(token, method, path, now_ts, nonce, sig, body) is True

  # Tampering with body or nonce invalidates signature
  assert verify_request_signature(token, method, path, now_ts, "other_nonce", sig, body) is False
  assert verify_request_signature(token, method, path, now_ts, nonce, sig, b'{"tampered": 1}') is False


# ============================================================================
# 2. Replay Protection & Timestamp Freshness
# ============================================================================


def test_t12_4_timestamp_freshness_window():
  """T12.4: Freshness window accepts ±60s drift and rejects stale timestamps."""
  now = time.time()

  # Within window
  assert validate_timestamp_freshness(now, now=now) is True
  assert validate_timestamp_freshness(now - 30.0, now=now) is True
  assert validate_timestamp_freshness(now + 45.0, now=now) is True

  # Outside window (drift > 60s)
  assert validate_timestamp_freshness(now - 61.0, now=now) is False
  assert validate_timestamp_freshness(now + 65.0, now=now) is False
  assert validate_timestamp_freshness("invalid-timestamp", now=now) is False


def test_t12_5_nonce_tracker_replay_detection():
  """T12.5: Nonce tracker detects replayed nonces and evicts expired entries."""
  tracker = NonceTracker(max_size=5, ttl=10.0)
  now = 1000.0

  # First addition succeeds
  assert tracker.check_and_add("nonce-1", now=now) is True
  # Duplicate addition fails (replay detected)
  assert tracker.check_and_add("nonce-1", now=now) is False

  # Distinct nonces succeed
  assert tracker.check_and_add("nonce-2", now=now) is True
  assert tracker.check_and_add("nonce-3", now=now) is True
  assert len(tracker) == 3

  # Advance time past TTL (now + 15s) -> previous nonces expire
  assert tracker.check_and_add("nonce-1", now=now + 15.0) is True


# ============================================================================
# 3. Device Authorization Registry
# ============================================================================


def test_t12_6_device_registry_lifecycle_and_atomic_persistence(tmp_path: Path):
  """T12.6: Device registry registration, token validation, revoking, and persistence."""
  reg_file = tmp_path / "devices.json"
  registry = DeviceRegistry(reg_file)

  dev_id = "device_alpha"
  dev_name = "Ken's Pixel 9"
  token = generate_bearer_token()

  # Register
  paired = registry.register_device(dev_id, dev_name, token)
  assert paired.device_id == dev_id
  assert paired.device_name == dev_name
  assert paired.token_hash == hash_token(token)

  # Validate token
  assert registry.validate_token(dev_id, token) is True
  assert registry.validate_token(dev_id, "wrong_token") is False
  assert registry.validate_token("unknown_device", token) is False

  # Reload from disk into new registry instance to verify atomic persistence
  reloaded = DeviceRegistry(reg_file)
  assert reloaded.is_device_known(dev_id) is True
  assert reloaded.validate_token(dev_id, token) is True
  devices = reloaded.list_devices()
  assert len(devices) == 1
  assert devices[0].device_name == dev_name

  # Revoke
  assert reloaded.revoke_device(dev_id) is True
  assert reloaded.is_device_known(dev_id) is False
  assert reloaded.validate_token(dev_id, token) is False

  # Re-check persistence of revocation
  reloaded_again = DeviceRegistry(reg_file)
  assert reloaded_again.is_device_known(dev_id) is False
  assert len(reloaded_again.list_devices()) == 0


# ============================================================================
# 4. Pairing Manager State Machine & Rate Limiting
# ============================================================================


def test_t12_7_pairing_manager_state_machine_and_ttl():
  """T12.7: PairingManager initiates session with TTL and detects expiration."""
  manager = PairingManager(ttl=2)
  assert manager.is_pairing_active is False

  data = manager.initiate_pairing(ttl=2, host="127.0.0.1", port=8000)
  assert manager.is_pairing_active is True
  assert len(data["pin"]) == 6
  assert "peit://pair?" in data["pairing_uri"]

  # Confirmation with invalid session
  ok, reason = manager.confirm_pairing("wrong_sess", "dev1", "proof")
  assert ok is False
  assert reason == "invalid_or_missing_session"

  # Sleep past TTL
  time.sleep(2.1)
  assert manager.is_pairing_active is False
  ok, reason = manager.confirm_pairing(data["session_id"], "dev1", "proof")
  assert ok is False
  assert reason == "session_expired"


def test_t12_8_pairing_manager_rate_limit_lockout():
  """T12.8: Failed pairing attempts trigger rate-limiting lockout after 3 tries."""
  manager = PairingManager(ttl=60)
  session_data = manager.initiate_pairing(ttl=60)
  sess_id = session_data["session_id"]

  # 1st failure
  ok1, r1 = manager.confirm_pairing(sess_id, "dev1", "bad_proof_1")
  assert ok1 is False
  assert r1 == "invalid_pin_proof"

  # 2nd failure
  ok2, r2 = manager.confirm_pairing(sess_id, "dev1", "bad_proof_2")
  assert ok2 is False
  assert r2 == "invalid_pin_proof"

  # 3rd failure -> triggers lockout and session invalidation
  ok3, r3 = manager.confirm_pairing(sess_id, "dev1", "bad_proof_3")
  assert ok3 is False
  assert r3 == "too_many_attempts"
  assert manager.is_pairing_active is False


# ============================================================================
# 5. REST API: Pairing Endpoints & Protected Sync
# ============================================================================


def test_t12_9_pairing_endpoints_happy_path(secure_server):
  """T12.9: Full handshake through POST /api/v1/pair/initiate and POST /api/v1/pair/confirm."""
  server, base_url, _, _ = secure_server

  # 1. Health shows auth_enabled=True, pairing_active=False
  status, health, _ = make_request(base_url, "/api/v1/health")
  assert status == 200
  assert health["auth_enabled"] is True
  assert health["pairing_active"] is False

  # 2. Initiate pairing session
  status_init, init_data, _ = make_request(
      base_url,
      "/api/v1/pair/initiate",
      method="POST",
      data={"ttl": 120},
  )
  assert status_init == 200
  assert init_data["status"] == "pairing_initiated"
  pin = init_data["pin"]
  salt = init_data["salt"]
  session_id = init_data["session_id"]
  assert "peit://pair?" in init_data["pairing_uri"]

  # Health now shows pairing_active=True
  _, health_active, _ = make_request(base_url, "/api/v1/health")
  assert health_active["pairing_active"] is True

  # 3. Client computes proof of PIN possession
  derived_key = derive_pairing_key(pin, salt)
  device_id = "device_test_001"
  device_name = "Mobile Test Client"
  pin_proof = compute_pin_proof(derived_key, session_id, device_id)

  # 4. Confirm pairing
  confirm_payload = {
      "session_id": session_id,
      "device_id": device_id,
      "device_name": device_name,
      "pin_proof": pin_proof,
  }
  status_conf, conf_data, _ = make_request(
      base_url,
      "/api/v1/pair/confirm",
      method="POST",
      data=confirm_payload,
  )
  assert status_conf == 200
  assert conf_data["status"] == "paired"
  assert conf_data["device_id"] == device_id
  auth_token = conf_data["auth_token"]
  assert len(auth_token) >= 32

  # Health now shows pairing_active=False (closed after success)
  _, health_closed, _ = make_request(base_url, "/api/v1/health")
  assert health_closed["pairing_active"] is False

  # 5. Device can now perform authenticated sync push
  sync_payload = {"entries": [sample_receipt_entry()]}
  headers = {
      "Authorization": f"Bearer {auth_token}",
      "X-PEIT-Device-ID": device_id,
      "X-PEIT-Timestamp": str(time.time()),
      "X-PEIT-Nonce": "nonce-alpha-1",
  }
  status_sync, sync_data, _ = make_request(
      base_url,
      "/api/v1/sync/push",
      method="POST",
      data=sync_payload,
      headers=headers,
  )
  assert status_sync == 200
  assert sync_data["status"] == "success"
  assert sync_data["imported"] == 1


def test_t12_10_pairing_confirm_failures(secure_server):
  """T12.10: Confirmation with incorrect proof or missing fields returns 400/401."""
  server, base_url, _, _ = secure_server

  # Initiate pairing
  _, init_data, _ = make_request(base_url, "/api/v1/pair/initiate", method="POST")
  session_id = init_data["session_id"]

  # Missing field -> 400
  bad_req_payload = {"session_id": session_id, "device_id": "d1"}
  status400, _, _ = make_request(
      base_url, "/api/v1/pair/confirm", method="POST", data=bad_req_payload
  )
  assert status400 == 400

  # Wrong proof -> 401
  bad_proof_payload = {
      "session_id": session_id,
      "device_id": "d1",
      "pin_proof": "deadbeef" * 8,
  }
  status401, data401, _ = make_request(
      base_url, "/api/v1/pair/confirm", method="POST", data=bad_proof_payload
  )
  assert status401 == 401
  assert data401["error"] == "unauthorized"


def test_t12_11_sync_push_security_enforcement(secure_server):
  """T12.11: Verification of 401 (unauthorized), 403 (revoked), and 400 (replay/expiry)."""
  server, base_url, _, _ = secure_server

  # Directly register an authorized device in the server registry
  dev_id = "device_registered"
  token = generate_bearer_token()
  server.device_registry.register_device(dev_id, "Registered Phone", token)

  entry_data = {"entries": [sample_receipt_entry()]}

  # 1. Missing Authorization / device ID headers -> 401
  status_no_auth, err1, _ = make_request(
      base_url, "/api/v1/sync/push", method="POST", data=entry_data
  )
  assert status_no_auth == 401
  assert err1["error"] == "unauthorized"

  # 2. Invalid bearer token -> 401
  headers_invalid_token = {
      "Authorization": "Bearer wrong-token-123",
      "X-PEIT-Device-ID": dev_id,
  }
  status_bad_tok, _, _ = make_request(
      base_url,
      "/api/v1/sync/push",
      method="POST",
      data=entry_data,
      headers=headers_invalid_token,
  )
  assert status_bad_tok == 401

  # 3. Unrecognized or revoked device -> 403
  headers_unknown_dev = {
      "Authorization": f"Bearer {token}",
      "X-PEIT-Device-ID": "device_unknown",
  }
  status_unknown, _, _ = make_request(
      base_url,
      "/api/v1/sync/push",
      method="POST",
      data=entry_data,
      headers=headers_unknown_dev,
  )
  assert status_unknown == 403

  # 4. Valid request succeeds -> 200
  fresh_nonce = "nonce-fresh-001"
  headers_valid = {
      "Authorization": f"Bearer {token}",
      "X-PEIT-Device-ID": dev_id,
      "X-PEIT-Timestamp": str(time.time()),
      "X-PEIT-Nonce": fresh_nonce,
  }
  status_ok, res_ok, _ = make_request(
      base_url,
      "/api/v1/sync/push",
      method="POST",
      data=entry_data,
      headers=headers_valid,
  )
  assert status_ok == 200
  assert res_ok["status"] == "success"

  # 5. Replayed nonce -> 400
  status_replay, res_replay, _ = make_request(
      base_url,
      "/api/v1/sync/push",
      method="POST",
      data=entry_data,
      headers=headers_valid,
  )
  assert status_replay == 400
  assert res_replay["error"] == "replayed_nonce"

  # 6. Stale timestamp (> 60s in the past) -> 400
  headers_stale = {
      "Authorization": f"Bearer {token}",
      "X-PEIT-Device-ID": dev_id,
      "X-PEIT-Timestamp": str(time.time() - 120.0),
      "X-PEIT-Nonce": "nonce-fresh-002",
  }
  status_stale, res_stale, _ = make_request(
      base_url,
      "/api/v1/sync/push",
      method="POST",
      data=entry_data,
      headers=headers_stale,
  )
  assert status_stale == 400
  assert res_stale["error"] == "request_expired"


def test_t12_12_insecure_lan_mode(tmp_path: Path):
  """T12.12: Server in secure=False mode permits unauthenticated sync push."""
  ledger_path = tmp_path / "insecure_ledger.jsonl"
  server = create_server(ledger_path, host="127.0.0.1", port=0, secure=False)
  port = server.server_address[1]
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  base_url = f"http://127.0.0.1:{port}"

  try:
    status_h, data_h, _ = make_request(base_url, "/api/v1/health")
    assert status_h == 200
    assert data_h["auth_enabled"] is False

    # Push without any auth headers succeeds
    payload = {"entries": [sample_receipt_entry()]}
    status_p, data_p, _ = make_request(
        base_url, "/api/v1/sync/push", method="POST", data=payload
    )
    assert status_p == 200
    assert data_p["status"] == "success"
    assert data_p["imported"] == 1
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3.0)


# ============================================================================
# 6. Self-Signed TLS Certificate Generation & Pinning
# ============================================================================


def test_t12_13_self_signed_tls_cert_generation(tmp_path: Path):
  """T12.13: Generate self-signed TLS cert, compute SHA-256 fingerprint."""
  cert_path = tmp_path / "test_cert.pem"
  key_path = tmp_path / "test_key.pem"

  fingerprint = generate_self_signed_cert(
      cert_path, key_path, host="127.0.0.1", days=30
  )
  assert cert_path.exists()
  assert key_path.exists()
  assert len(fingerprint.split(":")) == 32  # 32 colon-separated hex bytes

  # Reading fingerprint again returns identical value
  fp2 = get_cert_fingerprint(cert_path)
  assert fp2 == fingerprint


# ============================================================================
# 7. CLI Pairing and Device Management Integration
# ============================================================================


def test_t12_14_cli_device_management(tmp_path: Path, capsys):
  """T12.14: CLI flags --list-devices and --revoke-device."""
  reg_file = tmp_path / "cli_devices.json"
  registry = DeviceRegistry(reg_file)
  registry.register_device("cli_dev_1", "Tablet Pro", "tok1")

  # Test listing devices
  code = main(["--list-devices", "--device-registry", str(reg_file)])
  assert code == 0
  captured = capsys.readouterr()
  assert "cli_dev_1" in captured.out
  assert "Tablet Pro" in captured.out

  # Test revoking device
  code_rev = main(
      ["--revoke-device", "cli_dev_1", "--device-registry", str(reg_file)]
  )
  assert code_rev == 0
  fresh_reg = DeviceRegistry(reg_file)
  assert not fresh_reg.is_device_known("cli_dev_1")

  # Revoke non-existent device returns exit code 1
  code_non = main(
      ["--revoke-device", "cli_dev_1", "--device-registry", str(reg_file)]
  )
  assert code_non == 1
