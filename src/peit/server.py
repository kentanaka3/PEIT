"""
Desktop synchronization daemon for the Personal Economic Inflation Tracker (PEIT).

Provides a local-first, privacy-preserving HTTP REST server for syncing
receipt transactions between mobile devices, offline ledgers, and desktop analytics.
"""

from __future__ import annotations

import json
import logging
import signal
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

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
  """HTTP request handler providing REST API endpoints for PEIT sync."""

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
    """Handle GET requests for health, summary, and entries."""
    parsed = urlparse(self.path)
    path = parsed.path.rstrip("/")
    if not path:
      path = "/"
    params = parse_qs(parsed.query)

    if path in ("/api/v1/health", "/health"):
      self._handle_health()
    elif path in ("/api/v1/summary", "/summary"):
      self._handle_summary(params)
    elif path in ("/api/v1/entries", "/entries"):
      self._handle_entries(params)
    elif path == "/":
      self.send_json(
          200,
          {
              "service": "PEIT Synchronization Daemon",
              "status": "ok",
              "version": VERSION,
              "endpoints": [
                  "/api/v1/health",
                  "/api/v1/summary",
                  "/api/v1/entries",
                  "/api/v1/sync/push",
              ],
          },
      )
    else:
      self.send_json(
          404,
          {
              "error": "not_found",
              "message": f"Endpoint not found: {parsed.path}",
          },
      )

  def _handle_health(self) -> None:
    """Return daemon health, ledger info, and receipt schema column count."""
    with self.server.lock:
      count = get_ledger_entry_count(self.server.db)
    payload = {
        "status": "ok",
        "version": VERSION,
        "ledger": str(self.server.ledger_path),
        "entry_count": count,
        "schema_columns": len(RECEIPT_COLUMNS),
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
    """Handle POST requests for synchronization push."""
    parsed = urlparse(self.path)
    path = parsed.path.rstrip("/")
    if path in ("/api/v1/sync/push", "/sync/push"):
      self._handle_sync_push()
    else:
      self.send_json(
          404,
          {
              "error": "not_found",
              "message": f"Endpoint not found: {parsed.path}",
          },
      )

  def _handle_sync_push(self) -> None:
    """Process incoming receipt entries, validate against schema, and append."""
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
  """Threading HTTP server with attached LedgerDatabase instance and lock."""

  daemon_threads = True
  allow_reuse_address = True

  def __init__(
      self,
      server_address: tuple[str, int],
      RequestHandlerClass: type[BaseHTTPRequestHandler],
      ledger_path: str | Path,
  ):
    super().__init__(server_address, RequestHandlerClass)
    self.ledger_path = Path(ledger_path).resolve()
    self.db = LedgerDatabase(self.ledger_path)
    self.lock = threading.Lock()


def create_server(
    ledger_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> PEITHTTPServer:
  """Create and configure the PEIT ThreadingHTTPServer instance.

  Args:
    ledger_path: Path to authoritative JSONL ledger file.
    host: Host address interface (default: 127.0.0.1).
    port: Port number (default: 8000, or 0 for ephemeral OS assignment).

  Returns:
    Configured PEITHTTPServer instance.
  """
  return PEITHTTPServer(
      (host, port), PEITRequestHandler, ledger_path=ledger_path
  )


def run_server(
    ledger_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    broadcast: bool = True,
) -> None:
  """Run the synchronization daemon until interrupted by signal or shutdown."""
  server = create_server(ledger_path, host=host, port=port)
  actual_port = server.server_address[1]
  logger.info(
      "PEIT synchronization daemon running on http://%s:%d", host, actual_port
  )

  zc_registration = None
  if broadcast:
    zc_registration = register_zeroconf_service(actual_port)

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
