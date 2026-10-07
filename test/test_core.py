from peit.core import (
    REQUIRED,
    TIERS,
    ValidationIssue,
    calculate_indices,
    read_csv,
    validate_rows,
)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


def row(
    month,
    price,
    paid,
    item="milk",
    brand="",
    pack_size="1",
    store_tier="A",
    store_rating="5.0",
    brand_tier="A",
    brand_rating="5.0",
    product_tier="A",
    product_rating="5.0",
    availability="in_stock",
):
  return {
      "receipt_id": "r",
      "receipt_date": f"{month}-15",
      "merchant": "m",
      "item": item,
      "brand": brand,
      "category": "Food and beverages",
      "quantity": "1",
      "pack_size": str(pack_size),
      "unit": "L",
      "unit_price": str(price),
      "currency": "MXN",
      "discount": "0",
      "fee": "0",
      "tax": "0",
      "deposit": "0",
      "paid_total": str(paid),
      "event_type": "recurring",
      "store_tier": store_tier,
      "store_rating": str(store_rating),
      "brand_tier": brand_tier,
      "brand_rating": str(brand_rating),
      "product_tier": product_tier,
      "product_rating": str(product_rating),
      "availability": availability,
      "notes": "",
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
  # Base month:
  # 2 units of milk @ 20.00 and 1 unit of milk @ 26.00 ->
  # weighted price = (40 + 26) / 3 = 22.00
  base_rows = [
      {
          "receipt_id": "r1",
          "receipt_date": "2026-01-05",
          "merchant": "m",
          "item": "milk",
          "brand": "",
          "category": "Food and beverages",
          "quantity": "2",
          "pack_size": "1",
          "unit": "L",
          "unit_price": "20.00",
          "currency": "MXN",
          "discount": "0",
          "fee": "0",
          "tax": "0",
          "deposit": "0",
          "paid_total": "-40.00",
          "event_type": "recurring",
          "store_tier": "A",
          "store_rating": "5.0",
          "brand_tier": "A",
          "brand_rating": "5.0",
          "product_tier": "A",
          "product_rating": "5.0",
          "availability": "in_stock",
          "notes": "",
      },
      {
          "receipt_id": "r2",
          "receipt_date": "2026-01-15",
          "merchant": "m",
          "item": "milk",
          "brand": "",
          "category": "Food and beverages",
          "quantity": "1",
          "pack_size": "1",
          "unit": "L",
          "unit_price": "26.00",
          "currency": "MXN",
          "discount": "0",
          "fee": "0",
          "tax": "0",
          "deposit": "0",
          "paid_total": "-26.00",
          "event_type": "recurring",
          "store_tier": "A",
          "store_rating": "5.0",
          "brand_tier": "A",
          "brand_rating": "5.0",
          "product_tier": "A",
          "product_rating": "5.0",
          "availability": "in_stock",
          "notes": "",
      },
  ]
  # Month 2:
  # 1 unit of milk @ 33.00 ->
  # price index should be 100 * (33.00 / 22.00) = 150.0
  current_rows = [
      {
          "receipt_id": "r3",
          "receipt_date": "2026-02-10",
          "merchant": "m",
          "item": "milk",
          "brand": "",
          "category": "Food and beverages",
          "quantity": "1",
          "pack_size": "1",
          "unit": "L",
          "unit_price": "33.00",
          "currency": "MXN",
          "discount": "0",
          "fee": "0",
          "tax": "0",
          "deposit": "0",
          "paid_total": "-33.00",
          "event_type": "recurring",
          "store_tier": "A",
          "store_rating": "5.0",
          "brand_tier": "A",
          "brand_rating": "5.0",
          "product_tier": "A",
          "product_rating": "5.0",
          "availability": "in_stock",
          "notes": "",
      },
  ]
  result = calculate_indices(base_rows + current_rows)
  assert result[0]["fixed_basket_index"] == 100.0
  assert result[1]["fixed_basket_index"] == 150.0


def test_validation_schema_required_columns():
  r = row("2026-01", 2, -2)
  del r["brand"]
  issues = validate_rows([r])
  assert any(
      i.field == "brand" and i.message == "missing column" for i in issues
  )

  r2 = row("2026-01", 2, -2)
  del r2["pack_size"]
  issues2 = validate_rows([r2])
  assert any(
      i.field == "pack_size" and i.message == "missing column" for i in issues2
  )

  for field in (
      "store_tier",
      "store_rating",
      "brand_tier",
      "brand_rating",
      "product_tier",
      "product_rating",
      "availability",
  ):
    r_sub = row("2026-01", 2, -2)
    del r_sub[field]
    issues_sub = validate_rows([r_sub])
    assert any(
        i.field == field and i.message == "missing column" for i in issues_sub
    )


def test_validation_pack_size_rules():
  # Zero pack size
  r_zero = row("2026-01", 2, -2, pack_size="0")
  issues = validate_rows([r_zero])
  assert any(
      i.field == "pack_size" and i.message == "must be positive"
      for i in issues
  )

  # Negative pack size
  r_neg = row("2026-01", 2, -2, pack_size="-2")
  issues_neg = validate_rows([r_neg])
  assert any(
      i.field == "pack_size" and i.message == "must be positive"
      for i in issues_neg
  )

  # Non-numeric pack size
  r_alpha = row("2026-01", 2, -2, pack_size="pack")
  issues_alpha = validate_rows([r_alpha])
  assert any(
      i.field == "pack_size" and i.message == "must be numeric"
      for i in issues_alpha
  )

  # Empty string defaults to 1 (valid)
  r_empty = row("2026-01", 2, -2, pack_size="")
  assert validate_rows([r_empty]) == []

  # Multi-pack (valid)
  r_pack6 = row("2026-01", 2, -2, pack_size="6")
  assert validate_rows([r_pack6]) == []


def test_validation_date_and_types():
  # Invalid date
  r_bad_date = row("2026-01", 2, -2)
  r_bad_date["receipt_date"] = "2026-02-31"
  issues = validate_rows([r_bad_date])
  assert any(
      i.field == "receipt_date" and i.message == "must use YYYY-MM-DD"
      for i in issues
  )

  # Empty unit
  r_bad_unit = row("2026-01", 2, -2)
  r_bad_unit["unit"] = "  "
  issues = validate_rows([r_bad_unit])
  assert any(
      i.field == "unit" and i.message == "must not be empty" for i in issues
  )

  # Invalid currency
  r_bad_curr = row("2026-01", 2, -2)
  r_bad_curr["currency"] = "MXNN"
  issues = validate_rows([r_bad_curr])
  assert any(
      i.field == "currency" and i.message == "must be a three-letter code"
      for i in issues
  )


def test_validation_tier_domain():
  for field in ("store_tier", "brand_tier", "product_tier"):
    for valid_tier in ("A", "B", "C", "D", "E"):
      r = row("2026-01", 2, -2, **{field: valid_tier})
      assert validate_rows([r]) == []

    for invalid_tier in ("F", "premium", "a", "", "Z"):
      r = row("2026-01", 2, -2, **{field: invalid_tier})
      issues = validate_rows([r])
      assert any(
          i.field == field and i.message == "must be one of A, B, C, D, E"
          for i in issues
      )


def test_validation_rating_range():
  for field in ("store_rating", "brand_rating", "product_rating"):
    for valid_rating in ("1.0", "1", "2.5", "4.0", "5.0", 5.0, 3):
      r = row("2026-01", 2, -2, **{field: valid_rating})
      assert validate_rows([r]) == []

    # Rating < 1.0
    for low_rating in ("0.9", "0.0", "-1.0", 0.5):
      r = row("2026-01", 2, -2, **{field: low_rating})
      issues = validate_rows([r])
      assert any(
          i.field == field and i.message == "must be between 1.0 and 5.0"
          for i in issues
      )

    # Rating > 5.0
    for high_rating in ("5.1", "6.0", "10.0", 5.01):
      r = row("2026-01", 2, -2, **{field: high_rating})
      issues = validate_rows([r])
      assert any(
          i.field == field and i.message == "must be between 1.0 and 5.0"
          for i in issues
      )

    # Non-numeric rating
    for bad_rating in ("abc", "five", "", "None"):
      r = row("2026-01", 2, -2, **{field: bad_rating})
      issues = validate_rows([r])
      assert any(
          i.field == field and i.message == "must be between 1.0 and 5.0"
          for i in issues
      )


def test_validation_availability_status():
  for status in ("in_stock", "low_stock", "out_of_stock", "discontinued"):
    r = row("2026-01", 2, -2, availability=status)
    assert validate_rows([r]) == []

  for bad_status in ("available", "unavailable", "in stock", "unknown", ""):
    r = row("2026-01", 2, -2, availability=bad_status)
    issues = validate_rows([r])
    assert any(
        i.field == "availability" and i.message == "unsupported availability status"
        for i in issues
    )


def test_read_csv_on_migrated_data_and_schema():
  repo_root = Path(__file__).parents[1]
  schema_rows, schema_issues = read_csv(
      repo_root / "config" / "receipt_schema.csv"
  )
  assert len(schema_rows) == 1
  assert len(schema_issues) == 0
  for field in (
      "store_tier",
      "store_rating",
      "brand_tier",
      "brand_rating",
      "product_tier",
      "product_rating",
      "availability",
  ):
    assert field in schema_rows[0]

  example_rows, example_issues = read_csv(
      repo_root / "data" / "example_month.csv"
  )
  assert len(example_rows) == 10000
  assert len(example_issues) == 0
  for field in (
      "store_tier",
      "store_rating",
      "brand_tier",
      "brand_rating",
      "product_tier",
      "product_rating",
      "availability",
  ):
    assert field in example_rows[0]
