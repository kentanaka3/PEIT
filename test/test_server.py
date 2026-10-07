"""
Comprehensive integration and unit test suite for peit.server (Suite 9).

Tests the local synchronization daemon HTTP REST API:
- Health and status reporting
- Push synchronization, idempotency, and strict 25-column validation
- Transaction inquiries, category breakdowns, and financial summaries
- Server lifecycle and graceful shutdown
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from peit import __version__
from peit.cli import build_parser, main
from peit.core import REQUIRED
from peit.ledger import LedgerDatabase
from peit.server import PEITHTTPServer, create_server


def make_request(
    base_url: str,
    path: str,
    method: str = "GET",
    data: dict[str, Any] | list[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any, dict[str, str]]:
  """Helper to make HTTP requests against the local server using standard urllib."""
  req_headers = {"Accept": "application/json"}
  if headers:
    req_headers.update(headers)

  body_bytes = None
  if data is not None:
    body_bytes = json.dumps(data).encode("utf-8")
    req_headers["Content-Type"] = "application/json"

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


def sample_entry(
    receipt_id: str = "rec-001",
    item: str = "milk 1 l",
    paid_total: float = -2.50,
    receipt_date: str = "2026-01-15",
    category: str = "Food and beverages",
    merchant: str = "Example Market",
    event_type: str = "recurring",
    account: str = "default:checking",
) -> dict[str, Any]:
  """Construct a fully compliant 25-column receipt entry dictionary."""
  return {
      "receipt_id": receipt_id,
      "receipt_date": receipt_date,
      "merchant": merchant,
      "item": item,
      "brand": "Example Brand",
      "category": category,
      "quantity": 1.0,
      "pack_size": 1.0,
      "unit": "L",
      "unit_price": abs(paid_total),
      "currency": "MXN",
      "discount": 0.0,
      "fee": 0.0,
      "tax": 0.0,
      "deposit": 0.0,
      "paid_total": paid_total,
      "event_type": event_type,
      "store_tier": "A",
      "store_rating": 4.8,
      "brand_tier": "B",
      "brand_rating": 4.5,
      "product_tier": "A",
      "product_rating": 5.0,
      "availability": "in_stock",
      "notes": "Illustrative data only",
      "account": account,
  }


@pytest.fixture
def running_server(tmp_path: Path):
  """Spins up a test server on a free ephemeral OS port."""
  ledger_path = tmp_path / "test_ledger.jsonl"
  server = create_server(ledger_path, host="127.0.0.1", port=0, secure=False)
  port = server.server_address[1]
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()

  base_url = f"http://127.0.0.1:{port}"
  yield server, base_url, ledger_path

  server.shutdown()
  server.server_close()
  thread.join(timeout=3.0)


# ============================================================================
# Suite 9: Synchronization Daemon Tests
# ============================================================================


def test_t9_1_health_endpoint(running_server):
  """T9.1: Health check returns status, version, schema columns, and count."""
  server, base_url, ledger_path = running_server

  # Test /api/v1/health
  status, data, _ = make_request(base_url, "/api/v1/health")
  assert status == 200
  assert data["status"] == "ok"
  assert data["version"] == __version__
  assert data["ledger"] == str(ledger_path.resolve())
  assert data["entry_count"] == 0
  assert data["schema_columns"] == 25

  # Test /health alias
  status_alias, data_alias, _ = make_request(base_url, "/health")
  assert status_alias == 200
  assert data_alias["status"] == "ok"
  assert data_alias["entry_count"] == 0


def test_t9_2_sync_push_valid_entries(running_server):
  """T9.2: Push valid 25-column receipt entries to daemon."""
  server, base_url, ledger_path = running_server

  entries = [
      sample_entry(receipt_id="rec-001", item="milk 1 l", paid_total=-2.50),
      sample_entry(receipt_id="rec-002", item="bread 500 g", paid_total=-3.00),
  ]
  payload = {
      "entries": entries,
      "force": False,
      "account": "default:checking",
  }

  status, data, _ = make_request(base_url, "/api/v1/sync/push", method="POST", data=payload)
  assert status == 200
  assert data["status"] == "success"
  assert data["imported"] == 2
  assert data["skipped"] == 0
  assert len(data["entry_ids"]) == 2

  # Check that health endpoint reflects updated entry count
  status_h, data_h, _ = make_request(base_url, "/api/v1/health")
  assert status_h == 200
  assert data_h["entry_count"] == 2


def test_t9_3_sync_push_idempotency(running_server):
  """T9.3: Pushing identical entries a second time returns skipped count."""
  server, base_url, _ = running_server

  entries = [
      sample_entry(receipt_id="rec-001", item="milk 1 l", paid_total=-2.50),
      sample_entry(receipt_id="rec-002", item="bread 500 g", paid_total=-3.00),
  ]
  payload = {"entries": entries, "force": False}

  # First push: 2 imported, 0 skipped
  status1, data1, _ = make_request(base_url, "/api/v1/sync/push", method="POST", data=payload)
  assert status1 == 200
  assert data1["imported"] == 2
  assert data1["skipped"] == 0

  # Second push: 0 imported, 2 skipped
  status2, data2, _ = make_request(base_url, "/api/v1/sync/push", method="POST", data=payload)
  assert status2 == 200
  assert data2["imported"] == 0
  assert data2["skipped"] == 2
  assert len(data2["entry_ids"]) == 2


def test_t9_4_sync_push_force_overwrite(running_server):
  """T9.4: Pushing with force=True re-imports entries without skipping."""
  server, base_url, _ = running_server

  entries = [
      sample_entry(receipt_id="rec-001", item="milk 1 l", paid_total=-2.50),
  ]
  payload1 = {"entries": entries, "force": False}
  make_request(base_url, "/api/v1/sync/push", method="POST", data=payload1)

  payload_force = {"entries": entries, "force": True}
  status, data, _ = make_request(base_url, "/api/v1/sync/push", method="POST", data=payload_force)
  assert status == 200
  assert data["imported"] == 1
  assert data["skipped"] == 0


def test_t9_5_sync_push_validation_failure(running_server):
  """T9.5: Malformed receipt rows fail validation and return HTTP 400 with issues."""
  server, base_url, _ = running_server

  # 1. Missing required column 'merchant'
  entry_bad_column = sample_entry()
  del entry_bad_column["merchant"]

  # 2. Invalid date format and negative quantity
  entry_bad_values = sample_entry(receipt_id="rec-002")
  entry_bad_values["receipt_date"] = "15-01-2026"
  entry_bad_values["quantity"] = -5.0

  payload = {"entries": [entry_bad_column, entry_bad_values]}
  status, data, _ = make_request(base_url, "/api/v1/sync/push", method="POST", data=payload)

  assert status == 400
  assert data["error"] == "validation_failed"
  assert "issues" in data
  assert len(data["issues"]) >= 2

  fields_with_issues = [issue["field"] for issue in data["issues"]]
  assert "merchant" in fields_with_issues


def test_t9_6_sync_push_empty_and_raw_list(running_server):
  """T9.6: Handles empty list and direct JSON list payload gracefully."""
  server, base_url, _ = running_server

  # Empty list
  status, data, _ = make_request(
      base_url, "/api/v1/sync/push", method="POST", data={"entries": []}
  )
  assert status == 200
  assert data["imported"] == 0
  assert data["skipped"] == 0

  # Direct list payload without wrapping object
  entries = [sample_entry(receipt_id="rec-list-1")]
  status2, data2, _ = make_request(
      base_url, "/api/v1/sync/push", method="POST", data=entries
  )
  assert status2 == 200
  assert data2["imported"] == 1


def test_t9_7_get_entries_filtering_and_pagination(running_server):
  """T9.7: Query ledger entries with filters and limit/offset pagination."""
  server, base_url, _ = running_server

  entries = [
      sample_entry(
          receipt_id="r1",
          receipt_date="2026-01-10",
          category="Groceries",
          merchant="ShopA",
          account="checking",
      ),
      sample_entry(
          receipt_id="r2",
          receipt_date="2026-01-20",
          category="Utilities",
          merchant="ShopB",
          account="checking",
      ),
      sample_entry(
          receipt_id="r3",
          receipt_date="2026-02-05",
          category="Groceries",
          merchant="ShopA",
          account="savings",
      ),
  ]
  make_request(base_url, "/api/v1/sync/push", method="POST", data={"entries": entries})

  # All entries
  status, all_entries, _ = make_request(base_url, "/api/v1/entries")
  assert status == 200
  assert isinstance(all_entries, list)
  assert len(all_entries) == 3

  # Filter by month
  status_m, jan_entries, _ = make_request(base_url, "/api/v1/entries?month=2026-01")
  assert status_m == 200
  assert len(jan_entries) == 2

  # Filter by category
  status_c, groc_entries, _ = make_request(base_url, "/api/v1/entries?category=Groceries")
  assert status_c == 200
  assert len(groc_entries) == 2

  # Filter by merchant
  status_merch, shopb_entries, _ = make_request(base_url, "/api/v1/entries?merchant=ShopB")
  assert status_merch == 200
  assert len(shopb_entries) == 1
  assert shopb_entries[0]["merchant"] == "ShopB"

  # Filter by account
  status_acc, sav_entries, _ = make_request(base_url, "/api/v1/entries?account=savings")
  assert status_acc == 200
  assert len(sav_entries) == 1
  assert sav_entries[0]["account"] == "savings"

  # Pagination: limit=1, offset=1
  status_pag, pag_entries, _ = make_request(base_url, "/api/v1/entries?limit=1&offset=1")
  assert status_pag == 200
  assert len(pag_entries) == 1
  assert pag_entries[0]["receipt_id"] == "r2"


def test_t9_8_summary_endpoint(running_server):
  """T9.8: Financial summary endpoint returns balance, breakdown, and indices."""
  server, base_url, _ = running_server

  entries = [
      sample_entry(
          receipt_id="r1",
          item="item-1",
          paid_total=-20.00,
          category="Food",
          event_type="recurring",
          receipt_date="2026-01-15",
      ),
      sample_entry(
          receipt_id="r2",
          item="salary",
          paid_total=100.00,
          category="Income",
          event_type="income",
          receipt_date="2026-01-01",
      ),
  ]
  make_request(base_url, "/api/v1/sync/push", method="POST", data={"entries": entries})

  # Test /api/v1/summary
  status, summary, _ = make_request(base_url, "/api/v1/summary")
  assert status == 200
  assert summary["status"] == "ok"
  assert "balance" in summary
  assert summary["balance"]["total_income"] == 100.00
  assert summary["balance"]["total_expenditure"] == 20.00
  assert summary["balance"]["net_balance"] == 80.00

  assert "category_breakdown" in summary
  assert len(summary["category_breakdown"]) == 1
  assert summary["category_breakdown"][0]["category"] == "Food"
  assert summary["category_breakdown"][0]["total_spent"] == 20.00

  assert "indices" in summary
  assert isinstance(summary["indices"], list)

  # Test alias /summary
  status_alias, summary_alias, _ = make_request(base_url, "/summary")
  assert status_alias == 200
  assert summary_alias["status"] == "ok"


def test_t9_9_service_info_and_options_cors(running_server):
  """T9.9: Root endpoint and CORS preflight OPTIONS response."""
  server, base_url, _ = running_server

  # Root endpoint
  status, root_data, _ = make_request(base_url, "/")
  assert status == 200
  assert root_data["status"] == "ok"
  assert "endpoints" in root_data

  # 404 for unknown endpoint
  status_404, err_data, _ = make_request(base_url, "/api/v1/unknown")
  assert status_404 == 404
  assert err_data["error"] == "not_found"

  # OPTIONS preflight
  status_opt, _, opt_headers = make_request(base_url, "/api/v1/sync/push", method="OPTIONS")
  assert status_opt == 204
  assert "Access-Control-Allow-Origin" in opt_headers


def test_t9_10_cli_serve_parsing_and_exclusivity():
  """T9.10: CLI parser accurately configures --serve, --host, --port, and --broadcast flags."""
  parser = build_parser()

  # Default flags with --serve
  args1 = parser.parse_args(["--serve"])
  assert args1.serve is True
  assert args1.host == "127.0.0.1"
  assert args1.port == 8000
  assert args1.broadcast is True
  assert args1.ledger is None

  # Custom host, port, --no-broadcast, and ledger
  args2 = parser.parse_args([
      "--serve",
      "--host", "0.0.0.0",
      "--port", "9090",
      "--no-broadcast",
      "--ledger", "custom.jsonl",
  ])
  assert args2.serve is True
  assert args2.host == "0.0.0.0"
  assert args2.port == 9090
  assert args2.broadcast is False
  assert str(args2.ledger) == "custom.jsonl"

  # Mutual exclusivity with --index
  code = main(["--serve", "--index", "data/example_month.csv"])
  assert code == 2


def test_t9_11_server_graceful_shutdown(tmp_path: Path):
  """T9.11: Daemon starts cleanly and shuts down without errors or orphaned threads."""
  ledger_path = tmp_path / "lifecycle.jsonl"
  server = create_server(ledger_path, host="127.0.0.1", port=0)
  port = server.server_address[1]

  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()

  # Verify daemon is listening
  status, data, _ = make_request(f"http://127.0.0.1:{port}", "/health")
  assert status == 200
  assert data["status"] == "ok"

  # Trigger shutdown
  server.shutdown()
  server.server_close()
  thread.join(timeout=3.0)

  assert not thread.is_alive()

