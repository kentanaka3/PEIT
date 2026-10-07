"""
Signed transaction ledger module for PEIT.

Provides authoritative append-only JSONL logging and automatic sibling SQLite
projection caching for indexed inquiries and financial balances.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from peit.core import (
    AVAILABILITY_STATUSES,
    EVENT_TYPES,
    MONTH_RE,
    read_csv,
    validate_rows,
)


def compute_entry_id(
    receipt_id: str,
    item: str,
    paid_total: float | str,
    receipt_date: str,
) -> str:
  """Compute deterministic SHA-256 hash for deduplication.

  Normalizes numeric values (e.g. -2.5, -2.50, and -2.500 produce the same hash)
  and strips whitespace from string components.
  """
  try:
    num_val = float(paid_total)
    norm_amount = f"{num_val:.6f}"
  except (ValueError, TypeError):
    norm_amount = str(paid_total).strip()

  raw = f"{str(receipt_id).strip()}|{str(item).strip()}|{norm_amount}|{str(receipt_date).strip()}"
  return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class LedgerEntry:
  """Represents a signed transaction entry in the PEIT ledger."""

  entry_id: str
  receipt_id: str
  receipt_date: str
  account: str
  merchant: str
  item: str
  brand: str
  category: str
  quantity: float
  pack_size: float
  unit: str
  unit_price: float
  currency: str
  discount: float
  fee: float
  tax: float
  deposit: float
  paid_total: float
  event_type: str
  store_tier: str = "A"
  store_rating: float = 5.0
  brand_tier: str = "A"
  brand_rating: float = 5.0
  product_tier: str = "A"
  product_rating: float = 5.0
  availability: str = "in_stock"
  notes: str = ""
  recorded_at: str = ""

  @property
  def month(self) -> str:
    """Derive YYYY-MM from receipt_date for monthly aggregation."""
    return self.receipt_date[:7]

  def to_dict(self) -> dict[str, Any]:
    """Serialize entry to dictionary with standard types."""
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> LedgerEntry:
    """Instantiate LedgerEntry from dictionary, converting numeric types."""
    item = str(data["item"])
    unit_price = float(data["unit_price"])

    return cls(
        entry_id=str(data["entry_id"]),
        receipt_id=str(data["receipt_id"]),
        receipt_date=str(data["receipt_date"]),
        account=str(data.get("account", "default:checking")),
        merchant=str(data["merchant"]),
        item=item,
        brand=str(data.get("brand", "") or ""),
        category=str(data["category"]),
        quantity=float(data["quantity"]),
        pack_size=float(data.get("pack_size", 1.0)),
        unit=str(data["unit"]),
        unit_price=unit_price,
        currency=str(data["currency"]),
        discount=float(data.get("discount", 0.0)),
        fee=float(data.get("fee", 0.0)),
        tax=float(data.get("tax", 0.0)),
        deposit=float(data.get("deposit", 0.0)),
        paid_total=float(data["paid_total"]),
        event_type=str(data["event_type"]),
        store_tier=str(data["store_tier"]),
        store_rating=float(data["store_rating"]),
        brand_tier=str(data["brand_tier"]),
        brand_rating=float(data["brand_rating"]),
        product_tier=str(data["product_tier"]),
        product_rating=float(data["product_rating"]),
        availability=str(data.get("availability", "in_stock")),
        notes=str(data.get("notes", "")),
        recorded_at=str(data["recorded_at"]),
    )


class LedgerDatabase:
  """SQLite cache projection for authoritative JSONL ledger."""

  def __init__(self, ledger_path: str | Path):
    self.jsonl_path = Path(ledger_path).resolve()
    self.db_path = self.jsonl_path.with_suffix(".db")
    self._ensure_cache_valid()

  def _get_connection(self) -> sqlite3.Connection:
    conn = sqlite3.connect(str(self.db_path))
    conn.row_factory = sqlite3.Row
    return conn

  def _init_schema(self, conn: sqlite3.Connection) -> None:
    with conn:
      conn.execute("PRAGMA journal_mode=WAL;")
      conn.execute("PRAGMA synchronous=NORMAL;")
      conn.execute("""
          CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT
          )
      """)
      conn.execute("""
          CREATE TABLE IF NOT EXISTS entries (
              entry_id TEXT PRIMARY KEY,
              month TEXT NOT NULL,
              receipt_id TEXT NOT NULL,
              receipt_date TEXT NOT NULL,
              account TEXT NOT NULL,
              merchant TEXT NOT NULL,
              item TEXT NOT NULL,
              brand TEXT NOT NULL,
              category TEXT NOT NULL,
              quantity REAL NOT NULL,
              pack_size REAL NOT NULL,
              unit TEXT NOT NULL,
              unit_price REAL NOT NULL,
              currency TEXT NOT NULL,
              discount REAL NOT NULL,
              fee REAL NOT NULL,
              tax REAL NOT NULL,
              deposit REAL NOT NULL,
              paid_total REAL NOT NULL,
              event_type TEXT NOT NULL,
              store_tier TEXT NOT NULL,
              store_rating REAL NOT NULL,
              brand_tier TEXT NOT NULL,
              brand_rating REAL NOT NULL,
              product_tier TEXT NOT NULL,
              product_rating REAL NOT NULL,
              availability TEXT NOT NULL,
              notes TEXT NOT NULL,
              recorded_at TEXT NOT NULL
          )
      """)
      conn.execute(
          "CREATE INDEX IF NOT EXISTS idx_entries_month ON entries(month)")
      conn.execute(
          "CREATE INDEX IF NOT EXISTS idx_entries_receipt_date ON entries(receipt_date)")
      conn.execute(
          "CREATE INDEX IF NOT EXISTS idx_entries_account ON entries(account)")
      conn.execute(
          "CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category)")
      conn.execute(
          "CREATE INDEX IF NOT EXISTS idx_entries_merchant ON entries(merchant)")
      conn.execute(
          "CREATE INDEX IF NOT EXISTS idx_entries_event_type ON entries(event_type)")

  def _read_jsonl_entries(self) -> list[LedgerEntry]:
    if not self.jsonl_path.exists():
      return []
    entries: list[LedgerEntry] = []
    with self.jsonl_path.open("r", encoding="utf-8") as f:
      for line in f:
        line = line.strip()
        if not line:
          continue
        try:
          data = json.loads(line)
          entries.append(LedgerEntry.from_dict(data))
        except (json.JSONDecodeError, KeyError, ValueError):
          continue
    return entries

  def rebuild_cache(self) -> None:
    """Drop and recreate the SQLite projection cache from the JSONL log."""
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    if self.db_path.exists():
      try:
        self.db_path.unlink()
      except OSError:
        pass

    conn = self._get_connection()
    try:
      self._init_schema(conn)
      entries = self._read_jsonl_entries()
      if entries:
        self._insert_sqlite_batch(conn, entries, force=True)

      jsonl_mtime = str(self.jsonl_path.stat(
      ).st_mtime) if self.jsonl_path.exists() else "0"
      jsonl_size = str(self.jsonl_path.stat(
      ).st_size) if self.jsonl_path.exists() else "0"
      with conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("jsonl_mtime", jsonl_mtime)
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("jsonl_size", jsonl_size)
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("entry_count", str(len(entries)))
        )
    finally:
      conn.close()

  def _is_cache_valid(self) -> bool:
    if not self.db_path.exists():
      return False
    if not self.jsonl_path.exists():
      return True

    try:
      conn = self._get_connection()
      try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        )
        if not cur.fetchone():
          return False
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
        )
        if not cur.fetchone():
          return False

        cur.execute("SELECT value FROM meta WHERE key='jsonl_mtime'")
        row_mtime = cur.fetchone()
        cur.execute("SELECT value FROM meta WHERE key='jsonl_size'")
        row_size = cur.fetchone()

        if not row_mtime or not row_size:
          return False

        stat = self.jsonl_path.stat()
        stored_mtime = float(row_mtime[0])
        stored_size = int(row_size[0])

        if stat.st_size != stored_size or stat.st_mtime != stored_mtime:
          return False

        return True
      finally:
        conn.close()
    except (sqlite3.DatabaseError, ValueError):
      return False

  def _ensure_cache_valid(self) -> None:
    """Verify cache freshness and self-heal or rebuild if stale/corrupt."""
    if not self._is_cache_valid():
      self.rebuild_cache()

  def _insert_sqlite_batch(self, conn: sqlite3.Connection, entries: Iterable[LedgerEntry], force: bool = False) -> None:
    sql_op = "INSERT OR REPLACE" if force else "INSERT OR IGNORE"
    sql = f"""
        {sql_op} INTO entries (
            entry_id, month, receipt_id, receipt_date, account, merchant,
            item, brand, category, quantity, pack_size, unit, unit_price,
            currency, discount, fee, tax, deposit, paid_total, event_type,
            store_tier, store_rating, brand_tier, brand_rating, product_tier,
            product_rating, availability, notes, recorded_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """
    rows = [(
        e.entry_id, e.month, e.receipt_id, e.receipt_date, e.account,
        e.merchant, e.item, e.brand, e.category, e.quantity, e.pack_size,
        e.unit, e.unit_price, e.currency, e.discount, e.fee, e.tax, e.deposit,
        e.paid_total, e.event_type, e.store_tier, e.store_rating, e.brand_tier,
        e.brand_rating, e.product_tier, e.product_rating, e.availability,
        e.notes, e.recorded_at,
    ) for e in entries]
    with conn:
      conn.executemany(sql, rows)

  def get_existing_entry_ids(self) -> set[str]:
    """Retrieve all existing entry_ids from the projection cache."""
    self._ensure_cache_valid()
    conn = self._get_connection()
    try:
      cur = conn.execute("SELECT entry_id FROM entries")
      return {row[0] for row in cur.fetchall()}
    finally:
      conn.close()

  def append_entries(
      self, entries: list[LedgerEntry], force: bool = False
  ) -> tuple[int, int]:
    """Append entries to JSONL log and projection cache.

    Returns (imported_count, skipped_count).
    """
    self._ensure_cache_valid()
    existing_ids = self.get_existing_entry_ids()

    to_import: list[LedgerEntry] = []
    skipped_count = 0

    for e in entries:
      if e.entry_id in existing_ids and not force:
        skipped_count += 1
      else:
        to_import.append(e)
        if not force:
          existing_ids.add(e.entry_id)

    if not to_import:
      return 0, skipped_count

    # 1. Append to JSONL log
    self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with self.jsonl_path.open("a", encoding="utf-8") as f:
      for e in to_import:
        f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

    # 2. Update SQLite cache
    stat = self.jsonl_path.stat()
    conn = self._get_connection()
    try:
      self._insert_sqlite_batch(conn, to_import, force=force)
      cur = conn.execute("SELECT COUNT(*) FROM entries")
      total_count = cur.fetchone()[0]
      with conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("jsonl_mtime", str(stat.st_mtime))
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("jsonl_size", str(stat.st_size))
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("entry_count", str(total_count))
        )
    finally:
      conn.close()

    return len(to_import), skipped_count

  def get_balance(
      self, account: str | None = None, month: str | None = None
  ) -> dict[str, Any]:
    """Calculate financial balances across transactions."""
    self._ensure_cache_valid()
    conn = self._get_connection()
    try:
      where_clauses: list[str] = []
      params: list[Any] = []
      if account:
        where_clauses.append("account = ?")
        params.append(account)
      if month:
        where_clauses.append("month = ?")
        params.append(month)

      where_sql = (
          f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
      )

      cur = conn.execute(
          f"SELECT event_type, paid_total, month FROM entries {where_sql}",
          params,
      )
      rows = cur.fetchall()

      total_income = 0.0
      total_expenditure = 0.0
      net_transfers = 0.0
      net_refunds = 0.0
      net_balance = 0.0

      by_month: dict[str, dict[str, float]] = {}

      for row in rows:
        etype = row["event_type"]
        paid = float(row["paid_total"])
        m = row["month"]

        if m not in by_month:
          by_month[m] = {
              "total_income": 0.0,
              "total_expenditure": 0.0,
              "net_transfers": 0.0,
              "net_refunds": 0.0,
              "net_balance": 0.0,
          }

        net_balance += paid
        by_month[m]["net_balance"] += paid

        if etype == "income":
          total_income += paid
          by_month[m]["total_income"] += paid
        elif etype in ("recurring", "one_off"):
          # Expenditure reported as positive display amount
          exp_val = abs(paid)
          total_expenditure += exp_val
          by_month[m]["total_expenditure"] += exp_val
        elif etype == "transfer":
          net_transfers += paid
          by_month[m]["net_transfers"] += paid
        elif etype == "refund":
          net_refunds += paid
          by_month[m]["net_refunds"] += paid

      # Round all floats to 2 decimal places
      return {
          "total_income": round(total_income, 2),
          "total_expenditure": round(total_expenditure, 2),
          "net_transfers": round(net_transfers, 2),
          "net_refunds": round(net_refunds, 2),
          "net_balance": round(net_balance, 2),
          "by_month": {
              m: {k: round(v, 2) for k, v in metrics.items()}
              for m, metrics in sorted(by_month.items())
          },
      }
    finally:
      conn.close()

  def list_entries(
      self,
      month: str | None = None,
      category: str | None = None,
      merchant: str | None = None,
      event_type: str | None = None,
      account: str | None = None,
  ) -> list[LedgerEntry]:
    """Retrieve filterable transaction entries sorted chronologically."""
    self._ensure_cache_valid()
    conn = self._get_connection()
    try:
      where_clauses: list[str] = []
      params: list[Any] = []
      if month:
        where_clauses.append("month = ?")
        params.append(month)
      if category:
        where_clauses.append("category = ?")
        params.append(category)
      if merchant:
        where_clauses.append("merchant = ?")
        params.append(merchant)
      if event_type:
        where_clauses.append("event_type = ?")
        params.append(event_type)
      if account:
        where_clauses.append("account = ?")
        params.append(account)

      where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
      sql = f"SELECT * FROM entries {where_sql} ORDER BY receipt_date ASC, receipt_id ASC"

      cur = conn.execute(sql, params)
      return [LedgerEntry.from_dict(dict(row)) for row in cur.fetchall()]
    finally:
      conn.close()

  def get_category_breakdown(
      self,
      month: str | None = None,
      account: str | None = None,
  ) -> list[dict[str, Any]]:
    """Compute spending breakdown by category for consumption events."""
    self._ensure_cache_valid()
    conn = self._get_connection()
    try:
      where_clauses = ["event_type IN ('recurring', 'one_off')"]
      params: list[Any] = []
      if month:
        where_clauses.append("month = ?")
        params.append(month)
      if account:
        where_clauses.append("account = ?")
        params.append(account)

      where_sql = f"WHERE {' AND '.join(where_clauses)}"
      sql = f"""
          SELECT category, SUM(ABS(paid_total)) as total_spent, COUNT(*) as count
          FROM entries
          {where_sql}
          GROUP BY category
          ORDER BY total_spent DESC
      """
      cur = conn.execute(sql, params)
      rows = cur.fetchall()

      total_expenditure = sum(row["total_spent"] for row in rows)
      breakdown: list[dict[str, Any]] = []

      for row in rows:
        spent = row["total_spent"]
        pct = (
            spent / total_expenditure * 100.0
        ) if total_expenditure > 0 else 0.0
        breakdown.append({
            "category": row["category"],
            "total_spent": round(spent, 2),
            "percentage": round(pct, 2),
            "count": row["count"],
        })

      # Reconcile rounding differences on percentage so the sum equals 100.0%
      # if total_expenditure > 0
      if breakdown and total_expenditure > 0:
        sum_pct = round(sum(item["percentage"] for item in breakdown), 2)
        diff = round(100.0 - sum_pct, 2)
        if abs(diff) > 0.0 and abs(diff) < 0.1:
          breakdown[0]["percentage"] = round(
              breakdown[0]["percentage"] + diff, 2
          )

      return breakdown
    finally:
      conn.close()


# Module-level helper functions matching specification


def import_csv(
    ledger_path: str | Path,
    csv_path: str | Path,
    account: str = "default:checking",
    force: bool = False,
) -> tuple[int, int]:
  """Validate and import a CSV into the ledger.

  Returns (imported_count, skipped_count).
  Raises ValueError if CSV validation fails.
  """
  csv_file = Path(csv_path).resolve()
  rows, issues = read_csv(csv_file)
  if issues:
    messages = [
        f"Row {issue.row} [{issue.field}]: {issue.message}" for issue in issues
    ]
    raise ValueError(
        f"CSV validation failed with {len(issues)} issues:\n" +
        "\n".join(messages)
    )

  now_iso = datetime.now(timezone.utc).isoformat()
  entries: list[LedgerEntry] = []

  for r in rows:
    entry_id = compute_entry_id(
        receipt_id=r["receipt_id"],
        item=r["item"],
        paid_total=r["paid_total"],
        receipt_date=r["receipt_date"],
    )
    entry = LedgerEntry(
        entry_id=entry_id,
        receipt_id=r["receipt_id"],
        receipt_date=r["receipt_date"],
        account=account,
        merchant=r["merchant"],
        item=r["item"],
        brand=r.get("brand", ""),
        category=r["category"],
        quantity=float(r["quantity"]),
        pack_size=float(r.get("pack_size", 1.0)),
        unit=r["unit"],
        unit_price=float(r["unit_price"]),
        currency=r["currency"],
        discount=float(r.get("discount", 0.0)),
        fee=float(r.get("fee", 0.0)),
        tax=float(r.get("tax", 0.0)),
        deposit=float(r.get("deposit", 0.0)),
        paid_total=float(r["paid_total"]),
        event_type=r["event_type"],
        store_tier=r["store_tier"],
        store_rating=float(r["store_rating"]),
        brand_tier=r["brand_tier"],
        brand_rating=float(r["brand_rating"]),
        product_tier=r["product_tier"],
        product_rating=float(r["product_rating"]),
        availability=str(r.get("availability", "in_stock")),
        notes=r.get("notes", ""),
        recorded_at=now_iso,
    )
    entries.append(entry)

  db = LedgerDatabase(ledger_path)
  return db.append_entries(entries, force=force)


def add_entry(
    ledger_path: str | Path,
    receipt_date: str,
    amount: float | str,
    event_type: str,
    merchant: str,
    category: str = "General",
    item: str = "Transaction",
    brand: str = "",
    pack_size: float = 1.0,
    unit: str = "unit",
    quantity: float = 1.0,
    unit_price: float | None = None,
    currency: str = "MXN",
    account: str = "default:checking",
    store_tier: str = "A",
    store_rating: float = 5.0,
    brand_tier: str = "A",
    brand_rating: float = 5.0,
    product_tier: str = "A",
    product_rating: float = 5.0,
    availability: str = "in_stock",
    notes: str = "",
) -> LedgerEntry:
  """Validate and add a direct transaction entry to the ledger."""
  # Validate date
  try:
    d = date.fromisoformat(str(receipt_date))
  except ValueError:
    raise ValueError(
        f"Invalid receipt_date: {receipt_date}. Must be YYYY-MM-DD."
    )

  # Validate amount
  try:
    amount_float = float(amount)
  except (ValueError, TypeError):
    raise ValueError(f"Invalid amount: {amount}. Must be numeric.")

  # Validate event_type
  if event_type not in EVENT_TYPES:
    raise ValueError(
        f"Invalid event_type: {event_type}. Must be one of {sorted(EVENT_TYPES)}.")

  # Validate availability
  if availability not in AVAILABILITY_STATUSES:
    raise ValueError(
        f"Invalid availability: {availability}. Must be one of {sorted(AVAILABILITY_STATUSES)}."
    )

  # Validate tiers
  valid_tiers = {"A", "B", "C", "D", "E"}
  for t_name, t_val in [
      ("store_tier", store_tier),
      ("brand_tier", brand_tier),
      ("product_tier", product_tier),
  ]:
    if t_val not in valid_tiers:
      raise ValueError(
          f"Invalid tier ({t_name}): {t_val}. Must be one of {sorted(valid_tiers)}."
      )

  # Validate ratings
  for r_name, r_val in [
      ("store_rating", store_rating),
      ("brand_rating", brand_rating),
      ("product_rating", product_rating),
  ]:
    try:
      rf = float(r_val)
    except (ValueError, TypeError):
      raise ValueError(f"Invalid rating ({r_name}): {r_val}. Must be numeric.")
    if not (1.0 <= rf <= 5.0):
      raise ValueError(
          f"Invalid rating ({r_name}): {r_val}. Must be between 1.0 and 5.0."
      )

  # Validate currency
  if not re.fullmatch(r"[A-Za-z]{3}", currency):
    raise ValueError(f"Invalid currency: {currency}. Must be a 3-letter code.")

  # Format signed amount convention if needed
  # For expense (recurring/one_off), paid_total should be negative
  # For income/refund, paid_total should be positive
  # For transfer, signed amount as provided
  paid_total = amount_float
  if event_type in ("recurring", "one_off") and paid_total > 0:
    paid_total = -paid_total
  elif event_type in ("income", "refund") and paid_total < 0:
    paid_total = abs(paid_total)

  receipt_id = f"TXN-{d.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
  recorded_at = datetime.now(timezone.utc).isoformat()

  qty_float = float(quantity)
  # Calculate unit price if not provided
  calculated_unit_price = (
      abs(paid_total) / qty_float if qty_float > 0 else abs(paid_total)
  ) if unit_price is None else float(unit_price)

  entry_id = compute_entry_id(
      receipt_id=receipt_id,
      item=item,
      paid_total=paid_total,
      receipt_date=receipt_date,
  )

  entry = LedgerEntry(
      entry_id=entry_id,
      receipt_id=receipt_id,
      receipt_date=receipt_date,
      account=account,
      merchant=merchant,
      item=item,
      brand=brand,
      category=category,
      quantity=qty_float,
      pack_size=float(pack_size),
      unit=unit,
      unit_price=calculated_unit_price,
      currency=currency,
      discount=0.0,
      fee=0.0,
      tax=0.0,
      deposit=0.0,
      paid_total=paid_total,
      event_type=event_type,
      store_tier=store_tier,
      store_rating=float(store_rating),
      brand_tier=brand_tier,
      brand_rating=float(brand_rating),
      product_tier=product_tier,
      product_rating=float(product_rating),
      availability=availability,
      notes=notes,
      recorded_at=recorded_at,
  )

  db = LedgerDatabase(ledger_path)
  db.append_entries([entry], force=False)
  return entry


def get_balance(
    ledger_path: str | Path,
    account: str | None = None,
    month: str | None = None,
) -> dict[str, Any]:
  """Wrapper to query financial balance from LedgerDatabase."""
  db = LedgerDatabase(ledger_path)
  return db.get_balance(account=account, month=month)


def list_entries(
    ledger_path: str | Path,
    month: str | None = None,
    category: str | None = None,
    merchant: str | None = None,
    event_type: str | None = None,
    account: str | None = None,
) -> list[LedgerEntry]:
  """Wrapper to query filterable entries from LedgerDatabase."""
  db = LedgerDatabase(ledger_path)
  return db.list_entries(
      month=month,
      category=category,
      merchant=merchant,
      event_type=event_type,
      account=account,
  )


def get_category_breakdown(
    ledger_path: str | Path,
    month: str | None = None,
    account: str | None = None,
) -> list[dict[str, Any]]:
  """Wrapper to query category breakdown from LedgerDatabase."""
  db = LedgerDatabase(ledger_path)
  return db.get_category_breakdown(month=month, account=account)
