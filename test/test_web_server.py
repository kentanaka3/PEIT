"""
Comprehensive integration and unit test suite for PEIT Web Server (Suite 13).

Tests the local web server static file hosting and workbench routing:
- Root GET / serves index.html with 200 OK and text/html
- CSS assets (/css/theme.css, /css/workbench.css, /css/components.css) served with text/css
- JavaScript modules (/js/app.js, /js/store.js, components, islands) served with application/javascript
- Directory traversal attacks return 403 Forbidden or 404 Not Found
- API summary endpoint (/api/v1/summary) returns aggregated JSON
- Seamless coexistence with existing REST API endpoints
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from peit.server import PEITHTTPServer, create_server


def make_raw_request(
    base_url: str,
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
  """Helper to make HTTP requests returning raw bytes and response headers."""
  req_headers = {}
  if headers:
    req_headers.update(headers)

  req = urllib.request.Request(
      f"{base_url}{path}",
      headers=req_headers,
      method=method,
  )

  try:
    with urllib.request.urlopen(req) as resp:
      status = resp.status
      resp_headers = dict(resp.headers)
      raw = resp.read()
      return status, raw, resp_headers
  except urllib.error.HTTPError as err:
    status = err.code
    resp_headers = dict(err.headers)
    raw = err.read()
    return status, raw, resp_headers


@pytest.fixture
def running_web_server(tmp_path: Path):
  """Spins up a test server with project web directory on an ephemeral port."""
  ledger_path = tmp_path / "web_test_ledger.jsonl"
  repo_web = Path(__file__).resolve().parent.parent / "web"
  server = create_server(
      ledger_path,
      host="127.0.0.1",
      port=0,
      secure=False,
      web_root=repo_web,
  )
  port = server.server_address[1]
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()

  base_url = f"http://127.0.0.1:{port}"
  yield server, base_url, ledger_path

  server.shutdown()
  server.server_close()
  thread.join(timeout=3.0)


# ============================================================================
# Suite 13: Web Server & Static Workbench Hosting Tests
# ============================================================================


def test_t13_1_root_serves_workbench_html(running_web_server):
  """T13.1: GET / serves index.html with 200 OK and text/html."""
  server, base_url, _ = running_web_server

  status, raw, headers = make_raw_request(base_url, "/")
  assert status == 200
  content_type = headers.get("Content-Type", "")
  assert "text/html" in content_type
  html_text = raw.decode("utf-8")
  assert "PEIT WORKBENCH" in html_text
  assert "peit-activity-bar" in html_text
  assert "peit-data-grid" in html_text
  assert "peit-status-bar" in html_text


def test_t13_2_serves_css_assets(running_web_server):
  """T13.2: GET /css/theme.css and other CSS files return text/css."""
  server, base_url, _ = running_web_server

  for css_file in ("theme.css", "workbench.css", "components.css"):
    status, raw, headers = make_raw_request(base_url, f"/css/{css_file}")
    assert status == 200
    content_type = headers.get("Content-Type", "")
    assert "text/css" in content_type
    assert len(raw) > 50


def test_t13_3_serves_js_modules(running_web_server):
  """T13.3: GET /js/app.js, /js/store.js, and components return application/javascript."""
  server, base_url, _ = running_web_server

  js_paths = [
      "/js/app.js",
      "/js/store.js",
      "/js/components/activity_bar.js",
      "/js/components/data_grid.js",
      "/js/components/kpi_cards.js",
      "/js/components/status_bar.js",
      "/js/islands/flutter_island.js",
  ]
  for js_path in js_paths:
    status, raw, headers = make_raw_request(base_url, js_path)
    assert status == 200
    content_type = headers.get("Content-Type", "")
    assert "application/javascript" in content_type
    assert len(raw) > 30


def test_t13_4_directory_traversal_protection(running_web_server):
  """T13.4: Traversal attempts outside web/ are blocked with 403 Forbidden or 404 Not Found."""
  server, base_url, _ = running_web_server

  traversal_payloads = [
      "/../../etc/passwd",
      "/css/../../src/peit/schema.py",
      "/..%2f..%2fsrc/peit/schema.py",
      "/..%2f..%2f..%2fetc/hosts",
  ]
  for bad_path in traversal_payloads:
    status, raw, headers = make_raw_request(base_url, bad_path)
    # Must be 403 Forbidden or 404 Not Found, never 200
    assert status in (403, 404)
    # Crucially ensure source code / sensitive files are never leaked
    assert b"RECEIPT_COLUMNS" not in raw
    assert b"root:" not in raw


def test_t13_5_api_summary_returns_json(running_web_server):
  """T13.5: GET /api/v1/summary returns valid JSON with balance and categories."""
  server, base_url, _ = running_web_server

  status, raw, headers = make_raw_request(base_url, "/api/v1/summary")
  assert status == 200
  content_type = headers.get("Content-Type", "")
  assert "application/json" in content_type

  data = json.loads(raw.decode("utf-8"))
  assert data["status"] == "ok"
  assert "balance" in data
  assert "category_breakdown" in data
  assert "indices" in data
  assert "net_balance" in data


def test_t13_6_nonexistent_static_file_returns_404(running_web_server):
  """T13.6: Request for missing file returns structured 404 JSON."""
  server, base_url, _ = running_web_server

  status, raw, headers = make_raw_request(base_url, "/nonexistent_file.png")
  assert status == 404
  data = json.loads(raw.decode("utf-8"))
  assert data["error"] == "not_found"


def test_t13_7_serves_wasm_mime_type(running_web_server, tmp_path: Path):
  """T13.7: Static files ending in .wasm are served with application/wasm."""
  server, base_url, _ = running_web_server
  repo_web = Path(__file__).resolve().parent.parent / "web"
  flutter_dir = repo_web / "flutter"
  flutter_dir.mkdir(parents=True, exist_ok=True)
  sample_wasm = flutter_dir / "sample_engine.wasm"
  sample_wasm.write_bytes(b"\x00asm\x01\x00\x00\x00")

  try:
    status, raw, headers = make_raw_request(base_url, "/flutter/sample_engine.wasm")
    assert status == 200
    content_type = headers.get("Content-Type", "")
    assert "application/wasm" in content_type
    assert raw == b"\x00asm\x01\x00\x00\x00"
  finally:
    if sample_wasm.is_file():
      sample_wasm.unlink()
    if flutter_dir.is_dir() and not any(flutter_dir.iterdir()):
      flutter_dir.rmdir()


def test_t13_8_island_host_element_and_script(running_web_server):
  """T13.8: GET / serves peit-flutter-island component mount point and island script loads."""
  server, base_url, _ = running_web_server

  # Verify host DOM mount tag exists in index.html
  status, raw, headers = make_raw_request(base_url, "/")
  assert status == 200
  html_text = raw.decode("utf-8")
  assert "<peit-flutter-island>" in html_text
  assert 'id="view-flutter"' in html_text

  # Verify flutter_island.js is served with application/javascript
  status, raw, headers = make_raw_request(base_url, "/js/islands/flutter_island.js")
  assert status == 200
  content_type = headers.get("Content-Type", "")
  assert "application/javascript" in content_type
  js_code = raw.decode("utf-8")
  assert "FlutterIsland" in js_code
  assert "peit-flutter-island" in js_code
  assert "peit:island:message" in js_code


def test_t13_9_flutter_asset_traversal_blocked(running_web_server):
  """T13.9: Directory traversal targeting /flutter/ is safely rejected with 403 or 404."""
  server, base_url, _ = running_web_server

  attacks = [
      "/flutter/../../config/receipt_schema.csv",
      "/flutter/..%2f..%2fconfig/receipt_schema.csv",
      "/flutter/../../../src/peit/core.py",
  ]
  for attack in attacks:
    status, raw, headers = make_raw_request(base_url, attack)
    assert status in (403, 404)
    assert b"RECEIPT_COLUMNS" not in raw
    assert b"calculate_indices" not in raw


def test_t13_10_serves_extension_manifest_registry(running_web_server):
  """T13.10: GET /extensions/manifest_registry.json returns 200 OK and valid JSON."""
  server, base_url, _ = running_web_server

  status, raw, headers = make_raw_request(
      base_url, "/extensions/manifest_registry.json"
  )
  assert status == 200
  content_type = headers.get("Content-Type", "")
  assert "application/json" in content_type

  data = json.loads(raw.decode("utf-8"))
  assert "extensions" in data
  assert isinstance(data["extensions"], list)
  ext_ids = [ext["id"] for ext in data["extensions"]]
  assert "peit-crypto-cpi" in ext_ids
  assert "peit-carbon-footprint" in ext_ids


def test_t13_11_serves_extension_manifest_and_code(running_web_server):
  """T13.11: GET extension manifest and JS code returns 200 and proper MIME types."""
  server, base_url, _ = running_web_server

  # Manifest
  status, raw, headers = make_raw_request(
      base_url, "/extensions/peit-crypto-cpi/extension.json"
  )
  assert status == 200
  assert "application/json" in headers.get("Content-Type", "")
  manifest = json.loads(raw.decode("utf-8"))
  assert manifest["id"] == "peit-crypto-cpi"
  assert "contributes" in manifest
  assert "activityBar" in manifest["contributes"]

  # JS Entry module
  status, raw, headers = make_raw_request(
      base_url, "/extensions/peit-crypto-cpi/index.js"
  )
  assert status == 200
  assert "application/javascript" in headers.get("Content-Type", "")
  code = raw.decode("utf-8")
  assert "CryptoCpiView" in code
  assert "export async function activate" in code

  # Extension host module
  status, raw, headers = make_raw_request(
      base_url, "/js/extensions/extension_host.js"
  )
  assert status == 200
  assert "application/javascript" in headers.get("Content-Type", "")
  host_code = raw.decode("utf-8")
  assert "PeitExtensionHost" in host_code


def test_t13_12_serves_carbon_footprint_extension(running_web_server):
  """T13.12: GET carbon-footprint manifest and JS code returns 200 and valid content."""
  server, base_url, _ = running_web_server

  # Manifest
  status, raw, headers = make_raw_request(
      base_url, "/extensions/peit-carbon-footprint/extension.json"
  )
  assert status == 200
  assert "application/json" in headers.get("Content-Type", "")
  manifest = json.loads(raw.decode("utf-8"))
  assert manifest["id"] == "peit-carbon-footprint"

  # JS Entry module
  status, raw, headers = make_raw_request(
      base_url, "/extensions/peit-carbon-footprint/index.js"
  )
  assert status == 200
  assert "application/javascript" in headers.get("Content-Type", "")
  code = raw.decode("utf-8")
  assert "CarbonFootprintView" in code
  assert "CATEGORY_EMISSION_FACTORS" in code


def test_t13_13_extension_directory_traversal_blocked(running_web_server):
  """T13.13: Directory traversal attacks via /extensions/* are rejected with 403 or 404."""
  server, base_url, _ = running_web_server

  attacks = [
      "/extensions/../../config/receipt_schema.csv",
      "/extensions/peit-crypto-cpi/../../src/peit/schema.py",
      "/extensions/..%2f..%2fsrc/peit/core.py",
      "/extensions/..%2f..%2f..%2fetc/passwd",
  ]
  for attack in attacks:
    status, raw, headers = make_raw_request(base_url, attack)
    assert status in (403, 404)
    assert b"RECEIPT_COLUMNS" not in raw
    assert b"calculate_indices" not in raw
    assert b"root:" not in raw


def test_t13_14_workbench_and_mobile_fallback_resiliency(running_web_server):
  """T13.14: Verifies workbench connection banner and mobile web development fallback."""
  server, base_url, _ = running_web_server

  # Workbench index.html includes connection banner elements
  status, raw, headers = make_raw_request(base_url, "/")
  assert status == 200
  html = raw.decode("utf-8")
  assert "workbench-connection-banner" in html
  assert "banner-retry-btn" in html

  # Store module includes fallback summary and entries exports
  status, raw, headers = make_raw_request(base_url, "/js/store.js")
  assert status == 200
  store_code = raw.decode("utf-8")
  assert "FALLBACK_SUMMARY" in store_code
  assert "FALLBACK_ENTRIES" in store_code
  assert "fetchSnapshot" in store_code


def test_t13_15_single_http_response_frame_on_api_endpoints(running_web_server):
  """T13.15: API routes (/health, /summary, /entries) return exactly one HTTP response frame.

  Guards against dispatch fallthrough where an API response was previously followed
  by a secondary 404 response on the same HTTP stream.
  """
  import http.client
  import socket

  server, base_url, _ = running_web_server
  port = server.server_address[1]

  endpoints = [
      "/api/v1/health",
      "/health",
      "/api/v1/summary",
      "/summary",
      "/api/v1/entries",
      "/entries",
  ]

  for endpoint in endpoints:
    # 1. Test via raw socket to verify exactly one HTTP response header block
    sock = socket.create_connection(("127.0.0.1", port), timeout=5.0)
    try:
      req_bytes = f"GET {endpoint} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode("utf-8")
      sock.sendall(req_bytes)
      chunks = []
      while True:
        data = sock.recv(4096)
        if not data:
          break
        chunks.append(data)
      raw_resp = b"".join(chunks).decode("utf-8", errors="replace")

      # Count HTTP status lines in the response stream
      status_line_matches = [
          line for line in raw_resp.split("\r\n") if line.startswith("HTTP/1.0 200") or line.startswith("HTTP/1.1 200")
      ]
      error_line_matches = [
          line for line in raw_resp.split("\r\n") if "404 Not Found" in line or "404 not_found" in line
      ]
      assert len(status_line_matches) == 1, (
          f"Expected exactly 1 HTTP 200 status line for {endpoint}, got {len(status_line_matches)} in:\n{raw_resp}"
      )
      assert len(error_line_matches) == 0, (
          f"Found unexpected secondary 404 response for {endpoint} in raw stream:\n{raw_resp}"
      )
    finally:
      sock.close()

    # 2. Test via http.client
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
      conn.request("GET", endpoint)
      resp = conn.getresponse()
      assert resp.status == 200
      body = resp.read()
      data = json.loads(body.decode("utf-8"))
      assert isinstance(data, (dict, list))
    finally:
      conn.close()


def test_t13_16_serves_flutter_island_js(running_web_server):
  """T13.16: GET /js/islands/flutter_island.js serves valid JS with application/javascript."""
  server, base_url, _ = running_web_server

  status, raw, headers = make_raw_request(base_url, "/js/islands/flutter_island.js")
  assert status == 200
  content_type = headers.get("Content-Type", "")
  assert "application/javascript" in content_type
  code = raw.decode("utf-8")
  assert "FlutterIsland" in code
  assert "peit-flutter-island" in code
  assert "customElements.define" in code


def test_t13_17_virtualized_data_grid_contract(running_web_server):
  """T13.17: Virtualized data grid contains windowing, accessibility, and lifecycle contracts."""
  server, base_url, _ = running_web_server

  status, raw, _ = make_raw_request(base_url, "/js/components/data_grid.js")
  assert status == 200
  code = raw.decode("utf-8")
  assert "ROW_HEIGHT = 28" in code
  assert "OVERSCAN = 8" in code
  assert "grid-spacer" in code
  assert "AbortController" in code
  assert "ResizeObserver" in code
  assert "isVisible" in code
  assert "aria-sort" in code
  assert "grid-sort-btn" in code
  assert "column-resizer" in code


def test_t13_18_bounded_layout_and_containment_css(running_web_server):
  """T13.18: CSS includes 100dvh, flex containment, sticky exclusions for spacers, and resizers."""
  server, base_url, _ = running_web_server

  status, raw_wb, _ = make_raw_request(base_url, "/css/workbench.css")
  assert status == 200
  wb_css = raw_wb.decode("utf-8")
  assert "100dvh" in wb_css
  assert "#view-dashboard" in wb_css
  assert "#view-ledger" in wb_css

  status, raw_comp, _ = make_raw_request(base_url, "/css/components.css")
  assert status == 200
  comp_css = raw_comp.decode("utf-8")
  assert "peit-data-grid" in comp_css
  assert "contain: strict" in comp_css
  assert "column-resizer" in comp_css
  assert "tr:not(.grid-spacer)" in comp_css
  assert "grid-sort-btn" in comp_css


def test_t13_19_fallback_entries_canonical_schema_compliance():
  """T13.19: FALLBACK_ENTRIES in store.js strictly adheres to canonical schema (Defect #8).

  Verifies:
  - Outflows/expenses have negative paid_total.
  - Inflows/income have positive paid_total.
  - Surcharges (tax, fee, deposit) are non-positive.
  - event_type belongs to canonical EventType enums ('one_off', 'recurring', 'income', etc.).
  - store_tier, brand_tier, product_tier belong to QualityTier ('A', 'B', 'C', 'D', 'E').
  """
  import re
  from peit.schema import EventType, QualityTier

  store_path = Path(__file__).resolve().parent.parent / "web" / "js" / "store.js"
  content = store_path.read_text(encoding="utf-8")

  # Parse FALLBACK_ENTRIES from JS source using JSON-like extraction
  match = re.search(r"export const FALLBACK_ENTRIES\s*=\s*(\[[\s\S]*?\n\]);", content)
  assert match, "FALLBACK_ENTRIES definition not found in web/js/store.js"

  raw_entries_js = match.group(1)
  # Basic JS object syntax normalizer to json
  json_compatible = re.sub(r"(\w+):", r'"\1":', raw_entries_js)
  json_compatible = re.sub(r",\s*([}\]])", r"\1", json_compatible)
  entries = json.loads(json_compatible)

  assert len(entries) >= 4, "Expected at least 4 fallback entries"
  valid_event_types = {e.value for e in EventType}
  valid_tiers = {q.value for q in QualityTier}

  for entry in entries:
    event_type = entry.get("event_type")
    assert event_type in valid_event_types, f"Invalid event_type: {event_type}"
    paid_total = entry.get("paid_total")
    assert isinstance(paid_total, (int, float)), f"paid_total must be numeric: {paid_total}"

    if event_type == "income":
      assert paid_total > 0, f"Income paid_total must be positive: {paid_total}"
    elif event_type in ("one_off", "recurring"):
      assert paid_total < 0, f"Expense paid_total must be negative: {paid_total}"

    tax = entry.get("tax", 0.0)
    fee = entry.get("fee", 0.0)
    deposit = entry.get("deposit", 0.0)
    assert tax <= 0.0, f"Tax surcharge must be non-positive: {tax}"
    assert fee <= 0.0, f"Fee surcharge must be non-positive: {fee}"
    assert deposit <= 0.0, f"Deposit surcharge must be non-positive: {deposit}"

    for tier_key in ("store_tier", "brand_tier", "product_tier"):
      tier_val = entry.get(tier_key)
      assert tier_val in valid_tiers, f"Invalid {tier_key}: {tier_val}"


def test_t13_20_summary_indices_fixed_basket_index_parity(running_web_server, tmp_path: Path):
  """T13.20: /api/v1/summary endpoint returns valid indices with fixed_basket_index (Defect #9)."""
  from peit.ledger import LedgerDatabase, LedgerEntry
  from peit.schema import EventType, QualityTier, Availability

  server, base_url, ledger_path = running_web_server
  db = LedgerDatabase(ledger_path)

  # Insert two months of transactions to produce price indices
  e1 = LedgerEntry(
      entry_id="ENT-001",
      receipt_id="REC-2026-001",
      receipt_date="2026-08-01",
      account="checking",
      merchant="Dairy Mart",
      item="Milk",
      brand="BrandA",
      category="groceries",
      quantity=1.0,
      pack_size=1.0,
      unit="l",
      unit_price=20.0,
      currency="MXN",
      discount=0.0,
      fee=0.0,
      tax=0.0,
      deposit=0.0,
      paid_total=-20.0,
      event_type=EventType.ONE_OFF.value,
      store_tier=QualityTier.A.value,
      store_rating=5.0,
      brand_tier=QualityTier.A.value,
      brand_rating=5.0,
      product_tier=QualityTier.A.value,
      product_rating=5.0,
      availability=Availability.IN_STOCK.value,
      notes="Base month observation",
      recorded_at="2026-08-01T12:00:00Z",
  )

  e2 = LedgerEntry(
      entry_id="ENT-002",
      receipt_id="REC-2026-002",
      receipt_date="2026-09-01",
      account="checking",
      merchant="Dairy Mart",
      item="Milk",
      brand="BrandA",
      category="groceries",
      quantity=1.0,
      pack_size=1.0,
      unit="l",
      unit_price=24.0,
      currency="MXN",
      discount=0.0,
      fee=0.0,
      tax=0.0,
      deposit=0.0,
      paid_total=-24.0,
      event_type=EventType.ONE_OFF.value,
      store_tier=QualityTier.A.value,
      store_rating=5.0,
      brand_tier=QualityTier.A.value,
      brand_rating=5.0,
      product_tier=QualityTier.A.value,
      product_rating=5.0,
      availability=Availability.IN_STOCK.value,
      notes="Price rose 20%",
      recorded_at="2026-09-01T12:00:00Z",
  )

  db.append_entries([e1, e2])

  status, raw, headers = make_raw_request(base_url, "/api/v1/summary")
  assert status == 200
  data = json.loads(raw.decode("utf-8"))
  assert data["status"] == "ok"
  indices = data.get("indices", [])
  assert len(indices) == 2

  # August: base month
  aug_idx = indices[0]
  assert aug_idx["month"] == "2026-08"
  assert aug_idx["fixed_basket_index"] == 100.0

  # September: price rose 20 -> 24 (+20%)
  sep_idx = indices[1]
  assert sep_idx["month"] == "2026-09"
  assert sep_idx["fixed_basket_index"] == 120.0
  assert "changing_basket_expenditure_index" in sep_idx
  assert "coverage_percent" in sep_idx


def test_t13_21_multi_state_provenance_and_kpi_parity(running_web_server):
  """T13.21: Verifies multi-state provenance model, debouncing, and KPI cards contracts."""
  server, base_url, _ = running_web_server

  # 1. store.js contract
  status, raw, _ = make_raw_request(base_url, "/js/store.js")
  assert status == 200
  store_code = raw.decode("utf-8")
  assert 'transport: "checking"' in store_code
  assert 'dataSource: "unavailable"' in store_code
  assert 'freshness: "unknown"' in store_code
  assert "fetchSnapshot" in store_code
  assert "handleSnapshotFailure" in store_code
  assert "setTimeout" in store_code  # debounce & timeout

  # 2. kpi_cards.js contract
  status, raw, _ = make_raw_request(base_url, "/js/components/kpi_cards.js")
  assert status == 200
  kpi_code = raw.decode("utf-8")
  assert "fixed_basket_index" in kpi_code
  assert "changing_basket_expenditure_index" in kpi_code
  assert "Unavailable" in kpi_code
  assert "badge-neutral" in kpi_code
  assert "badge-warning" in kpi_code

  # 3. status_bar.js contract
  status, raw, _ = make_raw_request(base_url, "/js/components/status_bar.js")
  assert status == 200
  status_code = raw.decode("utf-8")
  assert "Live Daemon" in status_code
  assert "Offline Cache" in status_code
  assert "Demo Mode" in status_code


def test_t13_22_extension_api_hardening_and_integrity(running_web_server):
  """T13.22 (Phase D): Verifies extension sandbox hardening, schema alignment, and safe DOM."""
  server, base_url, _ = running_web_server

  # 1. Extension host sandbox contracts
  status, raw, _ = make_raw_request(base_url, "/js/extensions/extension_host.js")
  assert status == 200
  host_code = raw.decode("utf-8")
  assert "freezeEntryProjection" in host_code
  assert "Object.freeze" in host_code
  assert "Error in entry subscriber:" in host_code
  assert "rollbackExtension" in host_code
  assert "resolveViewTag" in host_code

  # 2. Reference extensions schema alignment and absence of nonexistent total_price
  for ext_path in [
      "/extensions/peit-carbon-footprint/index.js",
      "/extensions/peit-crypto-cpi/index.js",
  ]:
    status, raw, _ = make_raw_request(base_url, ext_path)
    assert status == 200
    ext_code = raw.decode("utf-8")
    assert "paid_total" in ext_code
    assert "total_price" not in ext_code
    assert "isConsumptionExpense" in ext_code
    assert "Demonstration" in ext_code
    # XSS Protection: safe DOM construction instead of innerHTML template interpolation
    assert "replaceChildren" in ext_code
    assert "innerHTML =" not in ext_code


def test_t13_23_phase_e_accessibility_and_shell_polish(running_web_server):
  """T13.23 (Phase E): Verifies WCAG 2.1 AA contrast tokens, keyboard navigation,

  status bar live regions, and reduced motion CSS media queries.
  """
  server, base_url, _ = running_web_server

  # 1. WCAG Contrast Color Tokens in theme.css
  status, raw, _ = make_raw_request(base_url, "/css/theme.css")
  assert status == 200
  theme_css = raw.decode("utf-8")
  assert "--md-sys-color-outline: #595c65;" in theme_css
  assert "--peit-color-rate-badge: #92400e;" in theme_css
  assert "--peit-color-income: #166534;" in theme_css
  assert "--peit-color-transfer: #1d4ed8;" in theme_css

  # 2. Activity Bar Accessibility Attributes & Keyboard Navigation
  status, raw, _ = make_raw_request(base_url, "/js/components/activity_bar.js")
  assert status == 200
  activity_bar_js = raw.decode("utf-8")
  assert 'role="tablist"' in activity_bar_js or 'role", "tablist"' in activity_bar_js
  assert 'aria-orientation="vertical"' in activity_bar_js or 'aria-orientation", "vertical"' in activity_bar_js
  assert 'role="tab"' in activity_bar_js
  assert "aria-selected" in activity_bar_js
  assert "aria-controls" in activity_bar_js
  assert "tabindex" in activity_bar_js
  assert "handleKeyDown" in activity_bar_js
  assert "ArrowDown" in activity_bar_js
  assert "ArrowUp" in activity_bar_js
  assert "Home" in activity_bar_js
  assert "End" in activity_bar_js

  # 3. Sidebar Toggle Accessibility & Keyboard Shortcut in app.js and index.html
  status, raw, _ = make_raw_request(base_url, "/js/app.js")
  assert status == 200
  app_js = raw.decode("utf-8")
  assert "initSidebarToggle" in app_js
  assert "aria-expanded" in app_js
  assert "peit_workbench_sidebar_collapsed" in app_js

  status, raw, _ = make_raw_request(base_url, "/")
  assert status == 200
  index_html = raw.decode("utf-8")
  assert 'id="sidebar-toggle-btn"' in index_html
  assert 'aria-controls="sidebar"' in index_html
  assert 'role="tabpanel"' in index_html

  # 4. Status Bar Live Regions & Screen Reader Announcements in status_bar.js
  status, raw, _ = make_raw_request(base_url, "/js/components/status_bar.js")
  assert status == 200
  status_bar_js = raw.decode("utf-8")
  assert 'role="region"' in status_bar_js or 'role", "region"' in status_bar_js
  assert 'role="status"' in status_bar_js
  assert 'aria-live="polite"' in status_bar_js
  assert 'aria-atomic="true"' in status_bar_js

  # 5. Reduced Motion and Responsive Media Queries in CSS files
  status, raw, _ = make_raw_request(base_url, "/css/workbench.css")
  assert status == 200
  workbench_css = raw.decode("utf-8")
  assert "prefers-reduced-motion: reduce" in workbench_css
  assert "animation-duration: 0.01ms !important;" in workbench_css
  assert "transition-duration: 0.01ms !important;" in workbench_css
  assert ".activity-item:focus-visible" in workbench_css
  assert "@media (max-width: 1024px)" in workbench_css

  status, raw, _ = make_raw_request(base_url, "/css/components.css")
  assert status == 200
  components_css = raw.decode("utf-8")
  assert "prefers-reduced-motion: reduce" in components_css
