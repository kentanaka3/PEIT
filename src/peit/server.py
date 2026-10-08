"""
Desktop synchronization daemon for the Personal Economic Inflation Tracker (PEIT).

Provides a local-first, privacy-preserving HTTP REST server for syncing
receipt transactions between mobile devices, offline ledgers, and desktop analytics.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import signal
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.parse import parse_qs, unquote, urlparse

from peit.auth import (
    DEFAULT_PAIRING_TTL_SECONDS,
    DeviceRegistry,
    NonceTracker,
    PairingManager,
    generate_bearer_token,
    generate_self_signed_cert,
    get_cert_fingerprint,
    validate_timestamp_freshness,
)
from peit.core import calculate_indices, validate_rows
from peit.ledger import LedgerDatabase, LedgerEntry
from peit.schema import EventType, RECEIPT_COLUMNS, compute_entry_id

VERSION = "0.1.0"
MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB payload limit for sync push

logger = logging.getLogger("peit.server")


def get_ledger_entry_count(db: LedgerDatabase) -> int:
  """Retrieve total entries count safely from the ledger database."""
  try:
    return len(db.get_existing_entry_ids())
  except Exception:
    return 0


class PEITRequestHandler(BaseHTTPRequestHandler):
  """HTTP request handler providing REST API endpoints and web workbench static serving."""

  server: PEITHTTPServer

  def log_message(self, format: str, *args: Any) -> None:
    """Route request logging through logger instead of raw stderr."""
    logger.debug(
        "%s - - [%s] %s",
        self.address_string(),
        self.log_date_time_string(),
        format % args,
    )

  def send_json(self, status_code: int, data: Any) -> None:
    """Send formatted JSON HTTP response with CORS headers."""
    encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    self.send_response(status_code)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(encoded)))
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header(
        "Access-Control-Allow-Headers", "Content-Type, Authorization"
    )
    self.end_headers()
    self.wfile.write(encoded)

  def do_OPTIONS(self) -> None:
    """Handle CORS preflight requests."""
    self.send_response(HTTPStatus.NO_CONTENT)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header(
        "Access-Control-Allow-Headers", "Content-Type, Authorization"
    )
    self.send_header("Content-Length", "0")
    self.end_headers()

  def do_GET(self) -> None:
    """Handle GET requests for health, summary, entries, and web static assets."""
    parsed = urlparse(self.path)
    clean_path = parsed.path.rstrip("/")
    if not clean_path:
      clean_path = "/"
    params = parse_qs(parsed.query)

    # 1. API routes
    if clean_path in ("/api/v1/health", "/health"):
      self._handle_health()
      return
    elif clean_path in ("/api/v1/summary", "/summary"):
      self._handle_summary(params)
      return
    elif clean_path in ("/api/v1/entries", "/entries"):
      self._handle_entries(params)
      return

    # Check if client explicitly asks for API root info via Accept: application/json
    accept_hdr = self.headers.get("Accept", "")
    if clean_path == "/" and "application/json" in accept_hdr and "text/html" not in accept_hdr:
      self._handle_api_root()
      return

    # 2. Static web asset routing (web workbench)
    if self._handle_static_file(parsed.path):
      return

    # 3. Fallback for root if web assets not present
    if clean_path == "/":
      self._handle_api_root()
      return

    # 4. Unknown endpoint
    self.send_json(
        404,
        {
            "error": "not_found",
            "message": f"Endpoint not found: {parsed.path}",
        },
    )

  def _handle_api_root(self) -> None:
    """Send API root information JSON."""
    self.send_json(
        200,
        {
            "service": "PEIT Synchronization Daemon",
            "status": "ok",
            "version": VERSION,
            "auth_enabled": self.server.secure,
            "pairing_active": self.server.pairing_manager.is_pairing_active,
            "endpoints": [
                "/api/v1/health",
                "/api/v1/summary",
                "/api/v1/entries",
                "/api/v1/sync/push",
                "/api/v1/pair/initiate",
                "/api/v1/pair/confirm",
            ],
        },
    )

  def _handle_static_file(self, raw_path: str) -> bool:
    """Serve static file from web_root with strict directory traversal protection.

    Returns True if handled (either served 200, 403, or 404), False if web_root not found.
    """
    web_root = self.server.web_root
    if not web_root or not web_root.is_dir():
      return False

    # Decode percent-encoding and normalize path
    unquoted = unquote(raw_path)
    rel_path = unquoted.lstrip("/")
    if not rel_path or rel_path == "index.html":
      target_file = web_root / "index.html"
    else:
      target_file = web_root / rel_path

    # Security check: Ensure canonical resolved path is strictly within web_root
    try:
      resolved_file = target_file.resolve()
      resolved_root = web_root.resolve()
      if not resolved_file.is_relative_to(resolved_root):
        self.send_json(
            403,
            {
                "error": "forbidden",
                "message": "Access denied: Directory traversal forbidden",
            },
        )
        return True
    except Exception:
      self.send_json(
          403,
          {
              "error": "forbidden",
              "message": "Access denied",
          },
      )
      return True

    # If directory requested, check for index.html
    if resolved_file.is_dir():
      resolved_file = resolved_file / "index.html"

    if not resolved_file.is_file():
      if raw_path == "/":
        return False
      self.send_json(
          404,
          {
              "error": "not_found",
              "message": f"File not found: {raw_path}",
          },
      )
      return True

    # Determine canonical MIME type
    if resolved_file.suffix == ".html":
      mime_type = "text/html"
    elif resolved_file.suffix == ".css":
      mime_type = "text/css"
    elif resolved_file.suffix == ".js":
      mime_type = "application/javascript"
    elif resolved_file.suffix == ".json":
      mime_type = "application/json"
    elif resolved_file.suffix == ".svg":
      mime_type = "image/svg+xml"
    elif resolved_file.suffix == ".wasm":
      mime_type = "application/wasm"
    elif resolved_file.suffix == ".png":
      mime_type = "image/png"
    elif resolved_file.suffix in (".jpg", ".jpeg"):
      mime_type = "image/jpeg"
    else:
      mime_type, _ = mimetypes.guess_type(str(resolved_file))
      if mime_type is None:
        mime_type = "application/octet-stream"

    # Add charset for text types
    if mime_type.startswith("text/") or mime_type in (
        "application/javascript",
        "application/json",
    ):
      content_type = f"{mime_type}; charset=utf-8"
    else:
      content_type = mime_type

    try:
      file_bytes = resolved_file.read_bytes()
      self.send_response(200)
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(len(file_bytes)))
      self.send_header("Access-Control-Allow-Origin", "*")
      self.send_header("Cache-Control", "no-cache")
      self.end_headers()
      self.wfile.write(file_bytes)
      return True
    except Exception as exc:
      logger.error("Error reading static file %s: %s", resolved_file, exc)
      self.send_json(
          500,
          {
              "error": "internal_server_error",
              "message": "Unable to read static file",
          },
      )
      return True

  def _handle_health(self) -> None:
    """Return daemon health, ledger info, auth status, and schema column count."""
    with self.server.lock:
      count = get_ledger_entry_count(self.server.db)
    payload = {
        "status": "ok",
        "version": VERSION,
        "ledger": str(self.server.ledger_path),
        "entry_count": count,
        "schema_columns": len(RECEIPT_COLUMNS),
        "auth_enabled": self.server.secure,
        "pairing_active": self.server.pairing_manager.is_pairing_active,
    }
    self.send_json(200, payload)

  def _handle_summary(self, params: dict[str, list[str]]) -> None:
    """Return balance summary, category breakdown, and price index calculations."""
    month = params.get("month", [None])[0]
    account = params.get("account", [None])[0]
    if account and account.lower() in ("all", "*", "none"):
      account = None

    db = self.server.db
    with self.server.lock:
      balance = db.get_balance(account=account, month=month)
      breakdown = db.get_category_breakdown(account=account, month=month)

      # Price and expenditure indices
      indices: list[dict[str, Any]] = []
      try:
        entries = db.list_entries(account=account, month=month)
        if entries:
          raw_rows = [e.to_dict() for e in entries]
          indices = calculate_indices(raw_rows)
      except Exception:
        indices = []

    payload = {
        "status": "ok",
        "balance": balance,
        "category_breakdown": breakdown,
        "indices": indices,
        "total_income": balance.get("total_income", 0.0),
        "total_expenditure": balance.get("total_expenditure", 0.0),
        "net_transfers": balance.get("net_transfers", 0.0),
        "net_refunds": balance.get("net_refunds", 0.0),
        "net_balance": balance.get("net_balance", 0.0),
        "by_month": balance.get("by_month", {}),
    }
    self.send_json(200, payload)

  def _handle_entries(self, params: dict[str, list[str]]) -> None:
    """Return serialized list of LedgerEntry objects with optional filters & pagination."""
    month = params.get("month", [None])[0]
    account = params.get("account", [None])[0]
    if account and account.lower() in ("all", "*", "none"):
      account = None
    category = params.get("category", [None])[0]
    merchant = params.get("merchant", [None])[0]
    event_type = params.get("event_type", [None])[0]

    offset = 0
    if "offset" in params:
      try:
        offset = max(0, int(params["offset"][0]))
      except ValueError:
        offset = 0

    limit = None
    if "limit" in params:
      try:
        limit = max(0, int(params["limit"][0]))
      except ValueError:
        limit = None

    db = self.server.db
    with self.server.lock:
      entries = db.list_entries(
          month=month,
          category=category,
          merchant=merchant,
          event_type=event_type,
          account=account,
      )

    sliced = entries[offset:]
    if limit is not None:
      sliced = sliced[:limit]

    payload = [e.to_dict() for e in sliced]
    self.send_json(200, payload)

  def do_POST(self) -> None:
    """Handle POST requests for sync push and device pairing."""
    parsed = urlparse(self.path)
    path = parsed.path.rstrip("/")
    if path in ("/api/v1/sync/push", "/sync/push"):
      self._handle_sync_push()
    elif path in ("/api/v1/pair/initiate", "/pair/initiate"):
      self._handle_pair_initiate()
    elif path in ("/api/v1/pair/confirm", "/pair/confirm"):
      self._handle_pair_confirm()
    else:
      self.send_json(
          404,
          {
              "error": "not_found",
              "message": f"Endpoint not found: {parsed.path}",
          },
      )

  def _read_json_body(self) -> tuple[Any, int | None]:
    """Read and decode incoming JSON request body.

    Returns (parsed_data, None) on success, or (None, http_status_code) on error.
    """
    content_length_hdr = self.headers.get("Content-Length")
    if not content_length_hdr:
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "Missing Content-Length header",
          },
      )
      return None, 400

    try:
      content_length = int(content_length_hdr)
    except ValueError:
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "Invalid Content-Length header",
          },
      )
      return None, 400

    if content_length > MAX_PAYLOAD_BYTES:
      self.send_json(
          413,
          {
              "error": "payload_too_large",
              "message": f"Payload size exceeds limit of {MAX_PAYLOAD_BYTES} bytes",
          },
      )
      return None, 413

    if content_length == 0:
      return {}, None

    raw_body = self.rfile.read(content_length)
    try:
      payload = json.loads(raw_body.decode("utf-8"))
      return payload, None
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
      self.send_json(
          400,
          {
              "error": "invalid_json",
              "message": f"Malformed JSON: {err}",
          },
      )
      return None, 400

  def _handle_pair_initiate(self) -> None:
    """Initiate a pairing session and return pairing credentials/URI."""
    ttl = DEFAULT_PAIRING_TTL_SECONDS
    # Check if request has body with optional ttl
    if self.headers.get("Content-Length"):
      payload, err = self._read_json_body()
      if err:
        return
      if isinstance(payload, dict) and "ttl" in payload:
        try:
          ttl = int(payload["ttl"])
        except (ValueError, TypeError):
          pass

    host = self.server.server_address[0]
    port = self.server.server_address[1]
    with self.server.lock:
      session_data = self.server.pairing_manager.initiate_pairing(
          ttl=ttl, host=host, port=port
      )

    logger.info("Initiated pairing session: %s (TTL: %ds)",
                session_data["session_id"], ttl)
    self.send_json(
        200,
        {
            "status": "pairing_initiated",
            "session_id": session_data["session_id"],
            "pin": session_data["pin"],
            "salt": session_data["salt"],
            "pairing_uri": session_data["pairing_uri"],
            "expires_at": session_data["expires_at"],
            "ttl": session_data["ttl"],
        },
    )

  def _handle_pair_confirm(self) -> None:
    """Verify PIN challenge-response proof and register device."""
    payload, err = self._read_json_body()
    if err:
      return

    if not isinstance(payload, dict):
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "Payload must be a JSON object",
          },
      )
      return

    session_id = str(payload.get("session_id", ""))
    device_id = str(payload.get("device_id", ""))
    device_name = str(payload.get("device_name", "") or device_id)
    pin_proof = str(payload.get("pin_proof", ""))

    if not session_id or not device_id or not pin_proof:
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "Missing required fields: session_id, device_id, pin_proof",
          },
      )
      return

    with self.server.lock:
      success, reason = self.server.pairing_manager.confirm_pairing(
          session_id=session_id,
          device_id=device_id,
          pin_proof=pin_proof,
      )

      if not success:
        logger.warning(
            "Pairing confirmation failed for device %s (session %s): %s",
            device_id,
            session_id,
            reason,
        )
        self.send_json(
            401,
            {
                "error": "unauthorized",
                "message": f"Pairing confirmation failed: {reason}",
                "reason": reason,
            },
        )
        return

      # Success: Generate bearer token and register device in registry
      auth_token = generate_bearer_token()
      device = self.server.device_registry.register_device(
          device_id=device_id,
          device_name=device_name,
          bearer_token=auth_token,
      )

    logger.info("Device '%s' successfully paired with server", device_id)
    self.send_json(
        200,
        {
            "status": "paired",
            "device_id": device.device_id,
            "device_name": device.device_name,
            "auth_token": auth_token,
        },
    )

  def _authenticate_sync_request(self) -> bool:
    """Authenticate and check replay protections for /api/v1/sync/push.

    Returns True if request is authorized, or False after sending error response.
    """
    if not self.server.secure:
      return True

    # 1. Check Authorization header
    auth_hdr = self.headers.get("Authorization", "")
    token = ""
    if auth_hdr.startswith("Bearer "):
      token = auth_hdr[7:].strip()

    device_id = self.headers.get("X-PEIT-Device-ID", "").strip()
    if not device_id or not token:
      self.send_json(
          401,
          {
              "error": "unauthorized",
              "message": "Missing Authorization Bearer token or X-PEIT-Device-ID header",
          },
      )
      return False

    with self.server.lock:
      # 2. Check if device is known and authorized
      if not self.server.device_registry.is_device_known(device_id):
        self.send_json(
            403,
            {
                "error": "forbidden",
                "message": f"Device '{device_id}' is revoked or not authorized",
            },
        )
        return False

      # 3. Check token validity
      if not self.server.device_registry.validate_token(device_id, token):
        self.send_json(
            401,
            {
                "error": "unauthorized",
                "message": "Invalid bearer token for device",
            },
        )
        return False

      # 4. Replay attack and timestamp freshness protection
      req_timestamp = self.headers.get("X-PEIT-Timestamp")
      if not req_timestamp:
        self.send_json(
            400,
            {
                "error": "missing_timestamp_header",
                "message": "Missing required 'X-PEIT-Timestamp' header",
            },
        )
        return False

      if not validate_timestamp_freshness(req_timestamp):
        self.send_json(
            400,
            {
                "error": "request_expired",
                "message": "Request timestamp drift exceeds allowed window (±60s)",
            },
        )
        return False

      req_nonce = self.headers.get("X-PEIT-Nonce")
      if not req_nonce:
        self.send_json(
            400,
            {
                "error": "missing_nonce_header",
                "message": "Missing required 'X-PEIT-Nonce' header",
            },
        )
        return False

      if not self.server.nonce_tracker.check_and_add(req_nonce):
        self.send_json(
            400,
            {
                "error": "replayed_nonce",
                "message": f"Nonce '{req_nonce}' has already been processed",
            },
        )
        return False

    return True

  def _handle_sync_push(self) -> None:
    """Process incoming receipt entries, validate against schema, and append."""
    if not self._authenticate_sync_request():
      return

    content_length_hdr = self.headers.get("Content-Length")
    if not content_length_hdr:
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "Missing Content-Length header",
          },
      )
      return

    try:
      content_length = int(content_length_hdr)
    except ValueError:
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "Invalid Content-Length header",
          },
      )
      return

    if content_length > MAX_PAYLOAD_BYTES:
      self.send_json(
          413,
          {
              "error": "payload_too_large",
              "message": f"Payload size exceeds limit of {MAX_PAYLOAD_BYTES} bytes",
          },
      )
      return

    raw_body = self.rfile.read(content_length)
    try:
      payload = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
      self.send_json(
          400,
          {
              "error": "invalid_json",
              "message": f"Malformed JSON: {err}",
          },
      )
      return

    if isinstance(payload, dict):
      entries_raw = payload.get("entries", [])
      force = bool(payload.get("force", False))
      account = str(payload.get("account", "default:checking"))
    elif isinstance(payload, list):
      entries_raw = payload
      force = False
      account = "default:checking"
    else:
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "Payload must be a JSON object or array",
          },
      )
      return

    if not isinstance(entries_raw, list):
      self.send_json(
          400,
          {
              "error": "bad_request",
              "message": "'entries' field must be a list",
          },
      )
      return

    if not entries_raw:
      self.send_json(
          200,
          {
              "status": "success",
              "imported": 0,
              "skipped": 0,
              "entry_ids": [],
          },
      )
      return

    # Verify each item is a dictionary
    for idx, item in enumerate(entries_raw):
      if not isinstance(item, dict):
        self.send_json(
            400,
            {
                "error": "validation_failed",
                "issues": [
                    {
                        "row": idx + 2,
                        "field": "entry",
                        "message": "Each entry must be a dictionary",
                    }
                ],
            },
        )
        return

    # Validate against strict 25-column receipt schema
    issues = validate_rows(entries_raw)
    if issues:
      issues_data = [
          {"row": issue.row, "field": issue.field, "message": issue.message}
          for issue in issues
      ]
      self.send_json(
          400,
          {
              "error": "validation_failed",
              "issues": issues_data,
          },
      )
      return

    # Convert to LedgerEntry
    now_iso = datetime.now(timezone.utc).isoformat()
    entries: list[LedgerEntry] = []
    entry_ids: list[str] = []

    for r in entries_raw:
      entry_id = str(r.get("entry_id") or compute_entry_id(
          receipt_id=str(r["receipt_id"]),
          item=str(r["item"]),
          paid_total=r["paid_total"],
          receipt_date=str(r["receipt_date"]),
      ))
      row_account = str(r.get("account") or account or "default:checking")
      entry = LedgerEntry(
          entry_id=entry_id,
          receipt_id=str(r["receipt_id"]),
          receipt_date=str(r["receipt_date"]),
          account=row_account,
          merchant=str(r["merchant"]),
          item=str(r["item"]),
          brand=str(r.get("brand", "") or ""),
          category=str(r["category"]),
          quantity=float(r["quantity"]),
          pack_size=float(r.get("pack_size", 1.0) or 1.0),
          unit=str(r["unit"]),
          unit_price=float(r["unit_price"]),
          currency=str(r["currency"]),
          discount=float(r.get("discount", 0.0) or 0.0),
          fee=float(r.get("fee", 0.0) or 0.0),
          tax=float(r.get("tax", 0.0) or 0.0),
          deposit=float(r.get("deposit", 0.0) or 0.0),
          paid_total=float(r["paid_total"]),
          event_type=str(r["event_type"]),
          store_tier=str(r.get("store_tier", "A") or "A"),
          store_rating=float(r.get("store_rating", 5.0) or 5.0),
          brand_tier=str(r.get("brand_tier", "A") or "A"),
          brand_rating=float(r.get("brand_rating", 5.0) or 5.0),
          product_tier=str(r.get("product_tier", "A") or "A"),
          product_rating=float(r.get("product_rating", 5.0) or 5.0),
          availability=str(r.get("availability", "in_stock") or "in_stock"),
          notes=str(r.get("notes", "") or ""),
          recorded_at=str(r.get("recorded_at") or now_iso),
      )
      entries.append(entry)
      entry_ids.append(entry_id)

    try:
      with self.server.lock:
        imported, skipped = self.server.db.append_entries(entries, force=force)
    except Exception as exc:
      logger.exception(
          "Failed to append entries into ledger database: %s", exc)
      self.send_json(
          500,
          {
              "error": "internal_server_error",
              "message": f"Failed to persist ledger entries: {exc}",
          },
      )
      return

    self.send_json(
        200,
        {
            "status": "success",
            "imported": imported,
            "skipped": skipped,
            "entry_ids": entry_ids,
        },
    )


class PEITHTTPServer(ThreadingHTTPServer):
  """Threading HTTP server with attached LedgerDatabase, security registry, lock, and web root."""

  daemon_threads = True
  allow_reuse_address = True

  def __init__(
      self,
      server_address: tuple[str, int],
      RequestHandlerClass: type[BaseHTTPRequestHandler],
      ledger_path: str | Path,
      secure: bool = True,
      device_registry_path: str | Path | None = None,
      certfile: str | Path | None = None,
      keyfile: str | Path | None = None,
      web_root: str | Path | None = None,
  ):
    super().__init__(server_address, RequestHandlerClass)
    self.ledger_path = Path(ledger_path).resolve()
    self.db = LedgerDatabase(self.ledger_path)
    self.lock = threading.Lock()
    self.secure = secure

    if device_registry_path is not None:
      reg_path = Path(device_registry_path).resolve()
    else:
      reg_path = self.ledger_path.parent / ".peit_paired_devices.json"
    self.device_registry = DeviceRegistry(reg_path)
    self.pairing_manager = PairingManager()
    self.nonce_tracker = NonceTracker()
    self.certfile = certfile
    self.keyfile = keyfile

    # Configure web assets root directory
    if web_root is not None:
      self.web_root: Path | None = Path(web_root).resolve()
    else:
      # Auto-detect default web directory at repository root or package parent
      candidate = Path.cwd() / "web"
      if candidate.is_dir():
        self.web_root = candidate.resolve()
      else:
        pkg_web = Path(__file__).resolve().parent.parent.parent / "web"
        self.web_root = pkg_web.resolve() if pkg_web.is_dir() else None

    # Configure TLS if certificates provided
    if certfile and keyfile:
      ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
      ssl_ctx.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
      self.socket = ssl_ctx.wrap_socket(self.socket, server_side=True)


def register_zeroconf_service(
    port: int,
    service_type: str = "_peit-sync._tcp.local.",
    properties: dict[str, str] | None = None,
) -> tuple[Any, Any] | None:
  """Register mDNS/Zeroconf service for PEIT desktop daemon.

  Returns a tuple of (Zeroconf, ServiceInfo) if successful, or None if zeroconf
  is not installed or failed to initialize.
  """
  try:
    from zeroconf import IPVersion, ServiceInfo, Zeroconf
  except ImportError:
    logger.info(
        "zeroconf package not installed; skipping local mDNS advertisement.")
    return None

  if properties is None:
    properties = {"version": VERSION, "schema": "25"}

  name = f"PEIT-Desktop-{port}.{service_type}"
  try:
    info = ServiceInfo(
        type_=service_type,
        name=name,
        port=port,
        properties=properties,
    )
    zc = Zeroconf(ip_version=IPVersion.V4Only)
    zc.register_service(info)
    logger.info("Registered mDNS service %s on port %d", name, port)
    return zc, info
  except Exception as exc:
    logger.warning(
        "Failed to register mDNS service: %s (falling back to direct IP)", exc)
    return None


def unregister_zeroconf_service(registration: tuple[Any, Any] | None) -> None:
  """Gracefully unregister Zeroconf service and close mDNS instance."""
  if not registration:
    return
  zc, info = registration
  try:
    zc.unregister_service(info)
    zc.close()
    logger.info("Unregistered mDNS service %s",
                getattr(info, "name", "unknown"))
  except Exception as exc:
    logger.warning("Error unregistering mDNS service: %s", exc)


def create_server(
    ledger_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    secure: bool = True,
    device_registry_path: str | Path | None = None,
    certfile: str | Path | None = None,
    keyfile: str | Path | None = None,
    web_root: str | Path | None = None,
) -> PEITHTTPServer:
  """Create and configure the PEIT ThreadingHTTPServer instance.

  Args:
    ledger_path: Path to authoritative JSONL ledger file.
    host: Host address interface (default: 127.0.0.1).
    port: Port number (default: 8000, or 0 for ephemeral OS assignment).
    secure: If True (default), enforce authorization tokens and replay protections on sync.
    device_registry_path: Optional path for device registry JSON.
    certfile: Optional path to PEM TLS certificate.
    keyfile: Optional path to PEM TLS private key.
    web_root: Optional path to directory containing frontend web assets.

  Returns:
    Configured PEITHTTPServer instance.
  """
  return PEITHTTPServer(
      (host, port),
      PEITRequestHandler,
      ledger_path=ledger_path,
      secure=secure,
      device_registry_path=device_registry_path,
      certfile=certfile,
      keyfile=keyfile,
      web_root=web_root,
  )


def run_server(
    ledger_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    broadcast: bool = True,
    secure: bool = True,
    device_registry_path: str | Path | None = None,
    certfile: str | Path | None = None,
    keyfile: str | Path | None = None,
    web_root: str | Path | None = None,
) -> None:
  """Run the synchronization daemon until interrupted by signal or shutdown."""
  server = create_server(
      ledger_path,
      host=host,
      port=port,
      secure=secure,
      device_registry_path=device_registry_path,
      certfile=certfile,
      keyfile=keyfile,
      web_root=web_root,
  )
  actual_port = server.server_address[1]
  proto = "https" if (certfile and keyfile) else "http"
  mode_str = "SECURE (Authenticated)" if secure else "INSECURE (No-auth)"
  logger.info(
      "PEIT synchronization daemon running on %s://%s:%d [%s]",
      proto,
      host,
      actual_port,
      mode_str,
  )

  zc_registration = None
  if broadcast:
    zc_properties = {
        "version": VERSION,
        "schema": "25",
        "secure": "1" if secure else "0",
        "tls": "1" if (certfile and keyfile) else "0",
    }
    zc_registration = register_zeroconf_service(
        actual_port, properties=zc_properties
    )

  def _sig_handler(signum: int, frame: Any) -> None:
    logger.info("Received signal %d, stopping server...", signum)
    threading.Thread(target=server.shutdown, daemon=True).start()

  if threading.current_thread() is threading.main_thread():
    for sig in (signal.SIGINT, signal.SIGTERM):
      try:
        signal.signal(sig, _sig_handler)
      except (ValueError, AttributeError):
        pass

  try:
    server.serve_forever()
  except (KeyboardInterrupt, SystemExit):
    pass
  finally:
    if zc_registration:
      unregister_zeroconf_service(zc_registration)
    server.server_close()
