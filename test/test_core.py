from peit.core import calculate_indices, validate_rows
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


def row(month, price, paid, item="milk"):
  return {
      "month": month, "receipt_id": "r", "receipt_date": f"{month}-15",
      "merchant": "m", "item_raw": item, "item_normalized": item,
      "category": "Food and beverages", "quantity": "1", "unit": "L",
      "shelf_unit_price": str(price), "currency": "MXN", "discount": "0",
      "fee": "0", "tax": "0", "deposit": "0", "paid_total": str(paid),
      "event_type": "recurring", "source_file": "x.csv", "notes": "",
  }


def test_validation_accepts_signed_expenditure():
  assert validate_rows([row("2026-01", 2, -2)]) == []


def test_indices_separate_price_and_expenditure():
  result = calculate_indices([
      row("2026-01", 2, -2),
      row("2026-02", 3, -6),
  ])
  assert result[1]["fixed_basket_index"] == 150.0
  assert result[1]["changing_basket_expenditure_index"] == 300.0
  assert result[1]["mom_percent"] == 50.0


def test_intra_month_duplicate_items_weighted_average():
  # Base month: 2 units of milk @ 20.00 and 1 unit of milk @ 26.00 -> weighted price = (40 + 26) / 3 = 22.00
  base_rows = [
      {
          "month": "2026-01", "receipt_id": "r1", "receipt_date": "2026-01-05",
          "merchant": "m", "item_raw": "milk", "item_normalized": "milk",
          "category": "Food and beverages", "quantity": "2", "unit": "L",
          "shelf_unit_price": "20.00", "currency": "MXN", "discount": "0",
          "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-40.00",
          "event_type": "recurring", "source_file": "x.csv", "notes": "",
      },
      {
          "month": "2026-01", "receipt_id": "r2", "receipt_date": "2026-01-15",
          "merchant": "m", "item_raw": "milk", "item_normalized": "milk",
          "category": "Food and beverages", "quantity": "1", "unit": "L",
          "shelf_unit_price": "26.00", "currency": "MXN", "discount": "0",
          "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-26.00",
          "event_type": "recurring", "source_file": "x.csv", "notes": "",
      },
  ]
  # Month 2: 1 unit of milk @ 33.00 -> price index should be 100 * (33.00 / 22.00) = 150.0
  current_rows = [
      {
          "month": "2026-02", "receipt_id": "r3", "receipt_date": "2026-02-10",
          "merchant": "m", "item_raw": "milk", "item_normalized": "milk",
          "category": "Food and beverages", "quantity": "1", "unit": "L",
          "shelf_unit_price": "33.00", "currency": "MXN", "discount": "0",
          "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-33.00",
          "event_type": "recurring", "source_file": "x.csv", "notes": "",
      },
  ]
  result = calculate_indices(base_rows + current_rows)
  assert result[0]["fixed_basket_index"] == 100.0
  assert result[1]["fixed_basket_index"] == 150.0
