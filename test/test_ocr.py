"""Comprehensive tests for Milestone 4A: Standalone Python OCR & Heuristic Parser."""

from __future__ import annotations

import json
from datetime import date
import pytest

from peit.core import REQUIRED, validate_rows
from peit.ledger import compute_entry_id
from peit.ocr import (
    BoundingBox,
    OCRTextBlock,
    ParsedLineItem,
    ParsedReceipt,
    ReceiptParser,
)


def test_bounding_box_properties():
    """Verify BoundingBox geometry calculations."""
    bbox = BoundingBox(x=10.0, y=20.0, width=50.0, height=30.0)
    assert bbox.right == 60.0
    assert bbox.bottom == 50.0
    assert bbox.center_x == 35.0
    assert bbox.center_y == 35.0


def test_bilingual_parsing_spanish_oxxo():
    """Test parsing typical Mexican convenience store slip (OXXO)."""
    raw_text = """
    CADENA COMERCIAL OXXO, S.A. DE C.V.
    CCO-860523-1N4
    OXXO REFORMA #1024
    FOLIO: 48291
    15/03/2026 14:32
    LECHE LALA ENTERA 1L        25.50
    PAN BIMBO BLANCO 680G       42.00
    COCA COLA 600ML             18.00
    SUBTOTAL                   85.50
    IVA 16%                     0.00
    TOTAL                      85.50
    EFECTIVO                  100.00
    CAMBIO                     14.50
    GRACIAS POR SU COMPRA
    """
    parser = ReceiptParser(default_currency="MXN")
    receipt = parser.parse_text(raw_text)

    assert receipt.merchant == "OXXO"
    assert receipt.store_id == "1024"
    assert receipt.receipt_date == "2026-03-15"
    assert receipt.currency == "MXN"
    assert "48291" in receipt.receipt_id
    assert len(receipt.items) == 3

    # Check items
    item_names = [it.item for it in receipt.items]
    assert any("LECHE LALA" in name for name in item_names)
    assert any("PAN BIMBO" in name for name in item_names)
    assert any("COCA COLA" in name for name in item_names)

    # Check arithmetic balancing
    assert receipt.subtotal == 85.50
    assert receipt.paid_total == 85.50
    assert receipt.is_balanced is True
    assert abs(receipt.balance_delta) < 0.01

    # Verify rows conversion and validation
    rows = receipt.to_peit_rows()
    assert len(rows) == 3
    issues = validate_rows(rows)
    assert len(issues) == 0

    # Ensure negative expense sign convention
    for row in rows:
        assert float(row["paid_total"]) < 0
        assert row["currency"] == "MXN"
        assert row["receipt_id"] == receipt.receipt_id
        assert row["receipt_date"] == "2026-03-15"
        assert row["merchant"] == "OXXO"


def test_bilingual_parsing_english_trader_joes():
    """Test parsing US supermarket receipt (Trader Joe's)."""
    raw_text = """
    TRADER JOE'S #542
    SAN FRANCISCO, CA
    March 15, 2026
    ORGANIC WHOLE MILK 1 GAL    4.99
    BANANAS                    1.29
    ALMOND BUTTER              6.49
    SUBTOTAL                  12.77
    SALES TAX                  0.00
    TOTAL                     12.77
    CREDIT CARD               12.77
    THANK YOU FOR SHOPPING!
    """
    parser = ReceiptParser(default_currency="USD")
    receipt = parser.parse_text(raw_text)

    assert receipt.merchant == "Trader Joe's"
    assert receipt.store_id == "542"
    assert receipt.receipt_date == "2026-03-15"
    assert receipt.currency == "USD"
    assert len(receipt.items) == 3
    assert receipt.paid_total == 12.77
    assert receipt.is_balanced is True

    rows = receipt.to_peit_rows()
    assert len(rows) == 3
    assert len(validate_rows(rows)) == 0


def test_date_format_variations():
    """Verify various date format extractions."""
    parser = ReceiptParser()

    # ISO
    r1 = parser.parse_text("WALMART\n2026-03-15\nITEM 10.00\nTOTAL 10.00")
    assert r1.receipt_date == "2026-03-15"

    # DD/MM/YYYY
    r2 = parser.parse_text("COSTCO\n15/03/2026\nITEM 10.00\nTOTAL 10.00")
    assert r2.receipt_date == "2026-03-15"

    # Spanish Month name: 15 MAR 2026 / 15 de marzo de 2026
    r3 = parser.parse_text("SORIANA\n15 MAR 2026\nITEM 10.00\nTOTAL 10.00")
    assert r3.receipt_date == "2026-03-15"

    r4 = parser.parse_text("CHEDRAUI\n15 de marzo de 2026\nITEM 10.00\nTOTAL 10.00")
    assert r4.receipt_date == "2026-03-15"

    # English Month name: March 15, 2026
    r5 = parser.parse_text("TARGET\nMarch 15, 2026\nITEM 10.00\nTOTAL 10.00")
    assert r5.receipt_date == "2026-03-15"


def test_spatial_line_item_clustering():
    """Test 2D spatial clustering of OCR text blocks with bounding boxes."""
    blocks = [
        # Line 0: Header
        OCRTextBlock("WALMART SUPERCENTER", BoundingBox(0.2, 0.05, 0.6, 0.03)),
        # Line 1: Date
        OCRTextBlock("2026-04-10", BoundingBox(0.3, 0.10, 0.4, 0.03)),
        # Line 2: Left description, Right price
        OCRTextBlock("ORGANIC EGGS 12 PK", BoundingBox(0.1, 0.20, 0.5, 0.03)),
        OCRTextBlock("45.50", BoundingBox(0.8, 0.205, 0.15, 0.029)),
        # Line 3: Left description, Right price
        OCRTextBlock("BREAD SOURDOUGH", BoundingBox(0.1, 0.25, 0.5, 0.03)),
        OCRTextBlock("35.00", BoundingBox(0.8, 0.252, 0.15, 0.028)),
        # Line 4: Total
        OCRTextBlock("TOTAL", BoundingBox(0.1, 0.35, 0.2, 0.03)),
        OCRTextBlock("80.50", BoundingBox(0.8, 0.351, 0.15, 0.03)),
    ]

    parser = ReceiptParser()
    receipt = parser.parse_blocks(blocks)

    assert receipt.merchant == "Walmart"
    assert receipt.receipt_date == "2026-04-10"
    assert len(receipt.items) == 2
    assert receipt.items[0].total_price == 45.50
    assert receipt.items[1].total_price == 35.00
    assert receipt.paid_total == 80.50
    assert receipt.is_balanced is True
    assert receipt.confidence >= 0.8


def test_multi_quantity_parsing():
    """Test multiple quantity patterns like '3 x 15.00'."""
    raw_text = """
    BODEGA AURRERA
    2026-05-01
    REFRESCO LATA
    3 x 15.00
    SUBTOTAL 45.00
    TOTAL 45.00
    """
    parser = ReceiptParser()
    receipt = parser.parse_text(raw_text)

    assert len(receipt.items) == 1
    item = receipt.items[0]
    assert item.quantity == 3.0
    assert item.unit_price == 15.00
    assert item.total_price == 45.00
    assert receipt.is_balanced is True

    # Inline quantity test
    raw_inline = """
    COSTCO
    2026-05-01
    CROISSANTS 2 x 20.00 40.00
    TOTAL 40.00
    """
    receipt_inline = parser.parse_text(raw_inline)
    assert len(receipt_inline.items) == 1
    assert receipt_inline.items[0].quantity == 2.0
    assert receipt_inline.items[0].unit_price == 20.00
    assert receipt_inline.items[0].total_price == 40.00
    assert receipt_inline.is_balanced is True


def test_arithmetic_balancing_and_discrepancy():
    """Test balancing logic when sums match vs when there is a discrepancy."""
    parser = ReceiptParser()

    # Balanced receipt
    balanced_text = """
    HEB
    2026-06-01
    ITEM A 10.00
    ITEM B 20.00
    SUBTOTAL 30.00
    IVA 4.80
    TOTAL 34.80
    """
    r_bal = parser.parse_text(balanced_text)
    assert r_bal.is_balanced is True
    assert abs(r_bal.balance_delta) < 0.01

    # Unbalanced receipt (e.g. OCR misread a price or tax)
    unbalanced_text = """
    HEB
    2026-06-01
    ITEM A 10.00
    ITEM B 20.00
    TOTAL 50.00
    """
    r_unbal = parser.parse_text(unbalanced_text)
    assert r_unbal.is_balanced is False
    assert r_unbal.balance_delta == 20.00


def test_to_peit_rows_schema_and_hashing():
    """Verify that to_peit_rows adheres to the strict 25-column schema and produces valid Ledger hashes."""
    raw_text = """
    CHEDRAUI #112
    2026-07-10
    MANZANA FUJI 1.500 kg x 40.00/kg 60.00
    AGUA BONAFONT 1L 15.00
    DESCUENTO 5.00
    TOTAL 70.00
    """
    parser = ReceiptParser()
    receipt = parser.parse_text(raw_text)

    rows = receipt.to_peit_rows()
    assert len(rows) == 2

    # Validate against strict PEIT schema
    issues = validate_rows(rows)
    assert len(issues) == 0

    for row in rows:
        for col in REQUIRED:
            assert col in row
        # Check signed amounts
        assert float(row["paid_total"]) < 0
        assert float(row["discount"]) >= 0

        # Deterministic hashing compatibility with Ledger
        entry_id = compute_entry_id(
            receipt_id=row["receipt_id"],
            item=row["item"],
            paid_total=row["paid_total"],
            receipt_date=row["receipt_date"],
        )
        assert len(entry_id) == 64


def test_json_serialization():
    """Verify JSON serialization and deserialization."""
    raw_text = "OXXO\n2026-01-01\nCAFE 25.00\nTOTAL 25.00"
    parser = ReceiptParser()
    receipt = parser.parse_text(raw_text)

    json_str = receipt.to_json()
    data = json.loads(json_str)

    assert data["merchant"] == "OXXO"
    assert data["receipt_date"] == "2026-01-01"
    assert len(data["items"]) == 1
    assert data["items"][0]["total_price"] == 25.0

