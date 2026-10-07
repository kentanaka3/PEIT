"""
Command-line interface for the Personal Economic Inflation Tracker (PEIT).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from peit.auth import DeviceRegistry, PairingManager, generate_self_signed_cert, get_cert_fingerprint
from peit.core import MONTH_RE, calculate_indices, read_csv
from peit.dashboard import create_dashboard, create_index_report
from peit.ledger import (
    LedgerDatabase,
    LedgerEntry,
    add_entry,
    get_balance,
    get_category_breakdown,
    import_csv,
    list_entries,
)
from peit.schema import Availability, EventType, QualityTier
from peit.server import create_server, run_server



def build_parser() -> argparse.ArgumentParser:
  """Construct and return the command-line argument parser for PEIT."""
  parser = argparse.ArgumentParser(
      prog="peit",
      description=(
          "Personal Economic Inflation Tracker (PEIT) - Command Line Interface"
      ),
  )

  # Primary operational modes
  mode_group = parser.add_argument_group("Primary Modes")
  mode_group.add_argument(
      "--index", type=Path, metavar="CSV_PATH",
      help=(
          "Calculate inflation indices from a monthly receipt CSV"
          "(supports --html, --json, -o, --open)"
      ),
  )
  mode_group.add_argument(
      "--ledger", type=Path, metavar="LEDGER_PATH",
      help=(
          "Path to authoritative JSONL ledger file"
          "(supports --html, --dashboard, --balance, --list, etc.)"
      ),
  )
  mode_group.add_argument(
      "--serve", action="store_true",
      help="Launch local synchronization daemon",
  )
  mode_group.add_argument(
      "--pair", action="store_true",
      help="Initiate an interactive 5-minute terminal pairing session for edge mobile devices",
  )
  mode_group.add_argument(
      "--list-devices", action="store_true",
      help="List all authorized edge mobile devices in the pairing registry",
  )
  mode_group.add_argument(
      "--revoke-device", type=str, metavar="DEVICE_ID",
      help="Revoke access for a specific authorized device ID",
  )

  # Server daemon options
  server_group = parser.add_argument_group("Server Daemon Options (for --serve / --pair)")
  server_group.add_argument(
      "--host", type=str, default="127.0.0.1", metavar="HOST",
      help="Host interface to bind synchronization daemon (default: %(default)s)",
  )
  server_group.add_argument(
      "--port", type=int, default=8000, metavar="PORT",
      help="Port to bind synchronization daemon (default: %(default)s)",
  )
  server_group.add_argument(
      "--broadcast", action=argparse.BooleanOptionalAction, default=True,
      help="Advertise service via mDNS/Zeroconf on local network (default: True, use --no-broadcast to disable)",
  )
  server_group.add_argument(
      "--insecure-lan", "--no-auth", action="store_true", dest="insecure_lan",
      help="Disable cryptographic authentication and allow unauthenticated sync push (developer mode)",
  )
  server_group.add_argument(
      "--device-registry", type=Path, metavar="PATH",
      help="Custom path to paired devices registry JSON (default: sibling .peit_paired_devices.json)",
  )
  server_group.add_argument(
      "--tls", action="store_true",
      help="Generate and enable self-signed TLS certificate for local HTTPS",
  )
  server_group.add_argument(
      "--cert", type=Path, metavar="CERT_PATH",
      help="Path to custom TLS certificate (PEM)",
  )
  server_group.add_argument(
      "--key", type=Path, metavar="KEY_PATH",
      help="Path to custom TLS private key (PEM)",
  )

  # Ledger operations
  ledger_group = parser.add_argument_group(
      "Ledger Operations (requires --ledger)")
  ledger_group.add_argument(
      "--import", dest="import_csv", type=Path, metavar="CSV_PATH",
      help="Import CSV receipts into the ledger",
  )
  ledger_group.add_argument(
      "--rebuild-cache", action="store_true",
      help="Rebuild sibling SQLite projection cache from JSONL log",
  )
  ledger_group.add_argument(
      "--add", action="store_true",
      help="Add a direct event/transaction to the ledger",
  )
  ledger_group.add_argument(
      "--balance", action="store_true",
      help="Compute financial balance summary",
  )
  ledger_group.add_argument(
      "--list", action="store_true",
      help="Query and list ledger transactions",
  )
  ledger_group.add_argument(
      "--breakdown", action="store_true",
      help="Compute category expenditure breakdown",
  )
  ledger_group.add_argument(
      "--dashboard", action="store_true",
      help=(
          "Generate interactive HTML5 multi-graph visualizer dashboard"
          "(alias: --html)"
      ),
  )

  # Filters & options
  filter_group = parser.add_argument_group("Filters & Options")
  filter_group.add_argument(
      "--html", action="store_true",
      help=(
          "Generate HTML output on demand"
          "(interactive dashboard for --ledger, HTML report for --index)"
      ),
  )
  filter_group.add_argument(
      "--month", type=str, metavar="YYYY-MM",
      help="Filter by month in YYYY-MM format",
  )
  filter_group.add_argument(
      "--category", type=str, metavar="CATEGORY",
      help="Filter by category (or specify category for --add)",
  )
  filter_group.add_argument(
      "--merchant", type=str, metavar="MERCHANT",
      help="Filter by merchant (or specify merchant for --add)",
  )
  filter_group.add_argument(
      "--event-type", type=str, metavar="EVENT_TYPE",
      help="Filter by event type (or specify event type for --add)",
  )
  filter_group.add_argument(
      "--account", type=str, default="default:checking", metavar="ACCOUNT",
      help="Account identifier (default: %(default)s)",
  )
  filter_group.add_argument(
      "--benchmark", type=Path, metavar="BENCHMARK_PATH",
      help="Path to national benchmark CPI CSV file",
  )
  filter_group.add_argument(
      "-o", "--output", type=Path, metavar="OUTPUT_PATH",
      help=(
          "Custom destination file path for generated HTML dashboard or report"
      ),
  )
  filter_group.add_argument(
      "--open", action="store_true",
      help="Open generated HTML dashboard or report in default web browser",
  )
  filter_group.add_argument(
      "--force", action="store_true",
      help="Force overwrite existing entries during import",
  )
  filter_group.add_argument(
      "--json", action="store_true",
      help="Emit machine-readable JSON output",
  )

  # Direct transaction addition arguments (for --add)
  add_group = parser.add_argument_group(
      "Direct Add Arguments (for --ledger ... --add)"
  )
  add_group.add_argument(
      "--date", type=str, metavar="YYYY-MM-DD",
      help="Transaction date (YYYY-MM-DD)",
  )
  add_group.add_argument(
      "--amount", type=float, metavar="AMOUNT",
      help="Signed transaction amount",
  )
  add_group.add_argument(
      "--item", type=str, default="Transaction", metavar="NAME",
      help="Normalized item key (default: %(default)s)",
  )
  add_group.add_argument(
      "--brand", type=str, default="", metavar="BRAND",
      help="Brand or manufacturer (default: empty)",
  )
  add_group.add_argument(
      "--pack-size", type=float, default=1.0, metavar="SIZE",
      help="Units per pack (default: %(default)s)",
  )
  add_group.add_argument(
      "--unit-price", type=float, default=None, metavar="PRICE",
      help="Unit price (calculated from amount/quantity if omitted)",
  )
  add_group.add_argument(
      "--notes", type=str, default="", metavar="TEXT",
      help="Optional transaction notes",
  )
  add_group.add_argument(
      "--store-tier", type=str, choices=["A", "B", "C", "D", "E"],
      default=None, metavar="STORE_TIER",
      help="Store tier bracket (choices: A, B, C, D, E; default: A)",
  )
  add_group.add_argument(
      "--store-rating", type=float, default=None, metavar="STORE_RATING",
      help="Store satisfaction rating between 1.0 and 5.0 (default: 5.0)",
  )
  add_group.add_argument(
      "--brand-tier", type=str, choices=["A", "B", "C", "D", "E"],
      default=None, metavar="BRAND_TIER",
      help="Brand tier bracket (choices: A, B, C, D, E; default: A)",
  )
  add_group.add_argument(
      "--brand-rating", type=float, default=None, metavar="BRAND_RATING",
      help="Brand satisfaction rating between 1.0 and 5.0 (default: 5.0)",
  )
  add_group.add_argument(
      "--product-tier", type=str, choices=["A", "B", "C", "D", "E"],
      default=None, metavar="PRODUCT_TIER",
      help="Product tier bracket (choices: A, B, C, D, E; default: A)",
  )
  add_group.add_argument(
      "--product-rating", type=float, default=None, metavar="PRODUCT_RATING",
      help="Product satisfaction rating between 1.0 and 5.0 (default: 5.0)",
  )
  add_group.add_argument(
      "--availability", type=str,
      choices=["in_stock", "low_stock", "out_of_stock", "discontinued"],
      default=None, metavar="AVAILABILITY",
      help="Item availability status (choices: in_stock, low_stock, out_of_stock, discontinued; default: in_stock)",
  )
  return parser


def format_index_table(report: list[dict[str, Any]]) -> str:
  """Format inflation index calculation results as a columnar ASCII table."""
  if not report:
    return "No inflation index data available."

  headers = [
      "month", "fixed_basket", "changing_expenditure", "coverage", "MoM"
  ]
  rows: list[list[str]] = []
  for item in report:
    fb = f"{item['fixed_basket_index']:.2f}" if item.get(
        "fixed_basket_index"
    ) is not None else "N/A"
    ce = f"{item['changing_basket_expenditure_index']:.2f}" if item.get(
        "changing_basket_expenditure_index"
    ) is not None else "N/A"
    cov = f"{item['coverage_percent']}%" if item.get(
        "coverage_percent"
    ) is not None else "N/A"
    mom = f"{item['mom_percent']}" if item.get(
        "mom_percent"
    ) is not None else "None"
    rows.append([str(item.get("month", "")), fb, ce, cov, mom])

  col_widths = [len(h) for h in headers]
  for r in rows:
    for i, val in enumerate(r):
      col_widths[i] = max(col_widths[i], len(val))

  header_str = " | ".join(
      h.ljust(col_widths[i]) for i, h in enumerate(headers)
  )
  separator = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
  row_strs = [" | ".join(
      val.rjust(col_widths[i]) if i > 0 else val.ljust(col_widths[i])
      for i, val in enumerate(r)
  ) for r in rows]
  return "\n".join([header_str, separator] + row_strs)


def format_balance_table(data: dict[str, Any]) -> str:
  """Format financial balance results as a clean ASCII summary table."""
  lines = [
      "=== Financial Balance Summary ===",
      f"Total Income:       {data.get('total_income', 0.0):>12.2f}",
      f"Total Expenditure:  {data.get('total_expenditure', 0.0):>12.2f}",
      f"Net Transfers:      {data.get('net_transfers', 0.0):>12.2f}",
      f"Net Refunds:        {data.get('net_refunds', 0.0):>12.2f}",
      "---------------------------------",
      f"Net Balance:        {data.get('net_balance', 0.0):>12.2f}",
  ]
  by_month = data.get("by_month", {})
  if by_month:
    lines.append("")
    lines.append("Monthly Breakdown:")
    headers = [
        "Month", "Income", "Expenditure", "Transfers", "Refunds", "Net Balance"
    ]
    m_rows = []
    for m, vals in sorted(by_month.items()):
      m_rows.append([
          m,
          f"{vals.get('total_income', 0.0):.2f}",
          f"{vals.get('total_expenditure', 0.0):.2f}",
          f"{vals.get('net_transfers', 0.0):.2f}",
          f"{vals.get('net_refunds', 0.0):.2f}",
          f"{vals.get('net_balance', 0.0):.2f}",
      ])
    widths = [len(h) for h in headers]
    for r in m_rows:
      for i, val in enumerate(r):
        widths[i] = max(widths[i], len(val))
    header_str = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "-+-".join("-" * widths[i] for i in range(len(headers)))
    r_strs = [" | ".join(
        val.rjust(widths[i]) if i > 0 else val.ljust(widths[i])
        for i, val in enumerate(r)
    ) for r in m_rows]
    lines.extend([header_str, sep] + r_strs)
  return "\n".join(lines)


def format_list_table(entries: list[LedgerEntry]) -> str:
  """Format transaction list as a clean columnar ASCII table."""
  if not entries:
    return "No matching transactions found."

  headers = [
      "Date", "Receipt ID", "Merchant", "Category", "Type", "Amount",
      "Account"
  ]
  rows = []
  for e in entries:
    rows.append([
        e.receipt_date,
        e.receipt_id,
        e.merchant,
        e.category,
        e.event_type,
        f"{e.paid_total:.2f}",
        e.account,
    ])
  widths = [len(h) for h in headers]
  for r in rows:
    for i, val in enumerate(r):
      widths[i] = max(widths[i], len(val))

  header_str = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
  sep = "-+-".join("-" * widths[i] for i in range(len(headers)))
  r_strs = [" | ".join(
      val.rjust(widths[i]) if i == 5 else val.ljust(widths[i])
      for i, val in enumerate(r)
  ) for r in rows]
  return "\n".join([header_str, sep] + r_strs)


def format_breakdown_table(breakdown: list[dict[str, Any]]) -> str:
  """Format category expenditure breakdown as a clean columnar ASCII table."""
  if not breakdown:
    return "No expenditure recorded."

  headers = ["Category", "Total Spent", "Percentage", "Count"]
  rows = []
  for b in breakdown:
    rows.append([
        str(b.get("category", "")),
        f"{b.get('total_spent', 0.0):.2f}",
        f"{b.get('percentage', 0.0):.2f}%",
        str(b.get("count", 0)),
    ])
  widths = [len(h) for h in headers]
  for r in rows:
    for i, val in enumerate(r):
      widths[i] = max(widths[i], len(val))

  header_str = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
  sep = "-+-".join("-" * widths[i] for i in range(len(headers)))
  r_strs = [" | ".join(
      val.rjust(widths[i]) if i > 0 else val.ljust(widths[i])
      for i, val in enumerate(r)
  ) for r in rows]
  return "\n".join([header_str, sep] + r_strs)


def main(argv: list[str] | None = None) -> int:
  """CLI entry point for PEIT."""
  parser = build_parser()
  try:
    args = parser.parse_args(argv)
  except SystemExit as exc:
    return exc.code if isinstance(exc.code, int) else 2

  # Helper to resolve device registry path
  def _get_registry_path() -> Path:
    if args.device_registry:
      return Path(args.device_registry).resolve()
    base_ledger = args.ledger if args.ledger else Path("data/ledger.jsonl")
    return Path(base_ledger).resolve().parent / ".peit_paired_devices.json"

  # Mode: List authorized devices
  if args.list_devices:
    reg_path = _get_registry_path()
    registry = DeviceRegistry(reg_path)
    devices = registry.list_devices()
    if not devices:
      print("No authorized devices found in registry.")
      return 0
    print(f"Authorized Paired Devices ({len(devices)}):")
    print(f"{'DEVICE ID':<36} {'DEVICE NAME':<20} {'PAIRED AT':<20} {'LAST SEEN':<20}")
    print("-" * 100)
    for d in devices:
      print(f"{d.device_id:<36} {d.device_name:<20} {d.paired_at:<20} {d.last_seen_at:<20}")
    return 0

  # Mode: Revoke authorized device
  if args.revoke_device:
    reg_path = _get_registry_path()
    registry = DeviceRegistry(reg_path)
    dev_id = args.revoke_device.strip()
    if registry.revoke_device(dev_id):
      print(f"Device '{dev_id}' successfully revoked from registry.")
      return 0
    else:
      sys.stderr.write(f"Error: Device '{dev_id}' not found in registry.\n")
      return 1

  # Mode: Interactive pairing session
  if args.pair:
    ledger_path = args.ledger if args.ledger else Path("data/ledger.jsonl")
    reg_path = _get_registry_path()
    host = args.host
    port = args.port
    secure = not args.insecure_lan

    server = create_server(
        ledger_path=ledger_path,
        host=host,
        port=port,
        secure=secure,
        device_registry_path=reg_path,
    )
    actual_port = server.server_address[1]
    session_data = server.pairing_manager.initiate_pairing(ttl=300, host=host, port=actual_port)

    print("=" * 64)
    print(" PEIT LAN PAIRING SECURITY HANDSHAKE")
    print("=" * 64)
    print(f"  One-Time 6-Digit PIN:  {session_data['pin']}")
    print(f"  Session ID:            {session_data['session_id']}")
    print(f"  Time-To-Live:          5 minutes (300 seconds)")
    print(f"  Pairing URI / QR:      {session_data['pairing_uri']}")
    print("=" * 64)
    print(f"Server listening on http://{host}:{actual_port} ...")
    print("Open the PEIT mobile app, scan or enter the 6-digit PIN.")
    print("Press Ctrl+C to cancel pairing.")

    import threading
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
      import time
      start_wait = time.time()
      while time.time() - start_wait < 300:
        time.sleep(1.0)
        # Check if paired
        with server.lock:
          if not server.pairing_manager.is_pairing_active:
            print("\nPairing handshake completed or expired.")
            break
    except KeyboardInterrupt:
      print("\nPairing session aborted by user.")
    finally:
      server.shutdown()
      server.server_close()
    return 0

  # Mode: Local synchronization daemon
  if args.serve:
    if args.index:
      sys.stderr.write("Error: Cannot specify both --index and --serve.\n")
      return 2
    ledger_path = args.ledger if args.ledger else Path("data/ledger.jsonl")
    reg_path = _get_registry_path()
    host = args.host
    port = args.port
    broadcast = bool(args.broadcast)
    secure = not args.insecure_lan

    cert_path = args.cert
    key_path = args.key
    if args.tls and (not cert_path or not key_path):
      tls_dir = Path.home() / ".peit" / "tls"
      tls_dir.mkdir(parents=True, exist_ok=True)
      cert_path = tls_dir / "peit_cert.pem"
      key_path = tls_dir / "peit_key.pem"
      if not cert_path.exists() or not key_path.exists():
        fingerprint = generate_self_signed_cert(cert_path, key_path, host=host)
        print(f"Generated self-signed TLS certificate at {cert_path}")
        print(f"Certificate SHA-256 Fingerprint: {fingerprint}")
      else:
        fingerprint = get_cert_fingerprint(cert_path)
        print(f"Using TLS certificate: {cert_path}")
        print(f"Certificate SHA-256 Fingerprint: {fingerprint}")

    proto = "https" if (cert_path and key_path) else "http"
    sec_mode = "SECURE (Authenticated)" if secure else "INSECURE LAN (No-auth)"
    print(f"Starting PEIT synchronization daemon on {proto}://{host}:{port} [{sec_mode}]")
    print(f"Authoritative ledger: {ledger_path}")
    print(f"Device registry: {reg_path}")
    print(f"Local mDNS broadcast: {'enabled' if broadcast else 'disabled'}")
    print("Press Ctrl+C to stop.")
    try:
      run_server(
          ledger_path=ledger_path,
          host=host,
          port=port,
          broadcast=broadcast,
          secure=secure,
          device_registry_path=reg_path,
          certfile=cert_path,
          keyfile=key_path,
      )
    except KeyboardInterrupt:
      print("\nDaemon stopped.")
    return 0

  # Validation: Exactly one primary mode
  if not args.index and not args.ledger:
    sys.stderr.write("Error: Must specify either --index or --ledger.\n")
    return 2

  if args.index and args.ledger:
    sys.stderr.write("Error: Cannot specify both --index and --ledger.\n")
    return 2

  # Filter validation: month
  if args.month and not MONTH_RE.match(args.month):
    sys.stderr.write(
        f"Error: Invalid month format '{args.month}'. Expected YYYY-MM.\n"
    )
    return 2

  # Handle account filter
  account_filter = None if (
      args.account and args.account.lower() in ("all", "*", "none")
  ) else args.account

  # Mode 1: Inflation index calculation
  if args.index:
    # Ensure ledger-specific operations are not given
    ledger_ops = [
        args.import_csv is not None,
        args.rebuild_cache,
        args.add,
        args.balance,
        args.list,
        args.breakdown,
    ]
    if any(ledger_ops):
      sys.stderr.write(
          "Error: Ledger operations cannot be used with --index.\n"
      )
      return 2

    if args.json and (args.html or args.dashboard):
      sys.stderr.write("Error: Cannot specify both --json and --html.\n")
      return 2

    if not args.index.exists():
      sys.stderr.write(f"Error: CSV file not found: {args.index}\n")
      return 2

    rows, issues = read_csv(args.index)
    if issues:
      for issue in issues:
        sys.stderr.write(f"row {issue.row}: {issue.field}: {issue.message}\n")
      return 2

    report = calculate_indices(rows)
    if args.html or args.dashboard:
      try:
        out = create_index_report(
            report=report,
            csv_path=args.index,
            output_path=args.output,
            open_browser=args.open,
        )
        print(f"Index HTML report generated successfully at: {out}")
        return 0
      except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2
    elif args.json:
      print(json.dumps(report, indent=2))
    else:
      print(format_index_table(report))
    return 0

  # Mode 2: Ledger operations
  assert args.ledger is not None

  op_flags = [
      args.import_csv is not None,
      args.rebuild_cache,
      args.add,
      args.balance,
      args.list,
      args.breakdown,
      args.dashboard or args.html,
  ]
  op_count = sum(bool(x) for x in op_flags)
  if op_count == 0:
    sys.stderr.write(
        "Error: Must specify one ledger operation: "
        "--import, --rebuild-cache, --add, --balance, --list, --breakdown, "
        "--dashboard, or --html.\n"
    )
    return 2
  if op_count > 1:
    sys.stderr.write(
        "Error: Only one ledger operation may be specified at a time.\n"
    )
    return 2

  # Operation 2a: Import CSV
  if args.import_csv is not None:
    if not args.import_csv.exists():
      sys.stderr.write(f"Error: CSV file not found: {args.import_csv}\n")
      return 2
    try:
      account = args.account if args.account else "default:checking"
      imported, skipped = import_csv(
          ledger_path=args.ledger,
          csv_path=args.import_csv,
          account=account,
          force=args.force,
      )
      print(f"Imported {imported} rows, skipped {skipped} duplicates.")
      return 0
    except ValueError as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2
    except Exception as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2

  # Operation 2b: Rebuild cache
  if args.rebuild_cache:
    try:
      db = LedgerDatabase(args.ledger)
      db.rebuild_cache()
      print(f"Cache rebuilt successfully for {args.ledger}.")
      return 0
    except Exception as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2

  # Operation 2c: Add event
  if args.add:
    missing: list[str] = []
    if not args.date:
      missing.append("--date")
    if args.amount is None:
      missing.append("--amount")
    if not args.event_type:
      missing.append("--event-type")
    if not args.merchant:
      missing.append("--merchant")

    if missing:
      sys.stderr.write(
          f"Error: Missing required argument(s) for --add: "
          f"{', '.join(missing)}\n"
      )
      return 2

    try:
      date.fromisoformat(args.date)
    except ValueError:
      sys.stderr.write(
          f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.\n")
      return 2

    allowed_event_types = [e.value for e in EventType]
    if args.event_type not in allowed_event_types:
      sys.stderr.write(
          f"Error: Invalid event-type '{args.event_type}'. Must be one of {sorted(allowed_event_types)}.\n"
      )
      return 2

    category = args.category if args.category else "General"
    item = args.item if args.item else "Transaction"
    brand = args.brand if args.brand else ""
    pack_size = float(args.pack_size) if args.pack_size is not None else 1.0
    unit_price = args.unit_price
    store_tier = args.store_tier or QualityTier.A.value
    store_rating = (
      float(args.store_rating) if args.store_rating is not None else 5.0
    )
    brand_tier = args.brand_tier or QualityTier.A.value
    brand_rating = (
      float(args.brand_rating) if args.brand_rating is not None else 5.0
    )
    product_tier = args.product_tier or QualityTier.A.value
    product_rating = (
      float(args.product_rating) if args.product_rating is not None else 5.0
    )
    availability = args.availability or Availability.IN_STOCK.value
    notes = args.notes if args.notes else ""
    account = args.account if args.account else "default:checking"

    for r_val, r_flag in [
        (args.store_rating, "--store-rating"),
        (args.brand_rating, "--brand-rating"),
        (args.product_rating, "--product-rating"),
    ]:
      if r_val is not None and not (1.0 <= float(r_val) <= 5.0):
        sys.stderr.write(f"Error: {r_flag} must be between 1.0 and 5.0\n")
        return 2

    try:
      entry = add_entry(
          ledger_path=args.ledger,
          receipt_date=args.date,
          amount=args.amount,
          event_type=args.event_type,
          merchant=args.merchant,
          category=category,
          item=item,
          brand=brand,
          pack_size=pack_size,
          unit_price=unit_price,
          account=account,
          store_tier=store_tier,
          store_rating=store_rating,
          brand_tier=brand_tier,
          brand_rating=brand_rating,
          product_tier=product_tier,
          product_rating=product_rating,
          availability=availability,
          notes=notes,
      )
      print(
          f"Added entry {entry.entry_id} ({entry.receipt_date} {entry.merchant} {entry.paid_total} {entry.currency}).")
      return 0
    except Exception as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2

  # Operation 2d: Balance
  if args.balance:
    try:
      data = get_balance(args.ledger, account=account_filter, month=args.month)
      if args.json:
        print(json.dumps(data, indent=2))
      else:
        print(format_balance_table(data))
      return 0
    except Exception as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2

  # Operation 2e: List
  if args.list:
    try:
      entries = list_entries(
          ledger_path=args.ledger,
          month=args.month,
          category=args.category,
          merchant=args.merchant,
          event_type=args.event_type,
          account=account_filter,
      )
      if args.json:
        print(json.dumps([e.to_dict() for e in entries], indent=2))
      else:
        print(format_list_table(entries))
      return 0
    except Exception as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2

  # Operation 2f: Breakdown
  if args.breakdown:
    try:
      data = get_category_breakdown(
          args.ledger, month=args.month, account=account_filter)
      if args.json:
        print(json.dumps(data, indent=2))
      else:
        print(format_breakdown_table(data))
      return 0
    except Exception as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2

  # Operation 2g: Dashboard / HTML
  if args.dashboard or args.html:
    try:
      out = create_dashboard(
          ledger_path=args.ledger,
          output_path=args.output,
          month=args.month,
          category=args.category,
          merchant=args.merchant,
          event_type=args.event_type,
          account=account_filter,
          benchmark_path=args.benchmark,
          open_browser=args.open,
      )
      print(f"Dashboard generated successfully at: {out}")
      return 0
    except Exception as e:
      sys.stderr.write(f"Error: {e}\n")
      return 2

  return 0


if __name__ == "__main__":
  sys.exit(main())
