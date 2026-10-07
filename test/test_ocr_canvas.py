"""Tests for Milestone 4B: Synthetic Receipt Image Generator & Distortion Simulator."""

from __future__ import annotations

import json
from pathlib import Path
from PIL import Image
import pytest

from peit.ocr import (
    BoundingBox,
    OCRTextBlock,
    ParsedReceipt,
    ReceiptCanvasGenerator,
    ReceiptParser,
    apply_distortions,
)
from peit.profiler.cli import generate_synthetic_receipt_image


def test_receipt_canvas_default_generation():
    """Verify default synthetic receipt image generation dimensions and types."""
    generator = ReceiptCanvasGenerator(canvas_width=500)
    image, blocks, gt_receipt = generator.generate_receipt()

    assert isinstance(image, Image.Image)
    assert image.mode == "RGB"
    assert image.size[0] == 500
    assert image.size[1] > 300

    assert len(blocks) > 0
    assert isinstance(gt_receipt, ParsedReceipt)
    assert gt_receipt.merchant == "OXXO"
    assert gt_receipt.is_balanced is True
    assert len(gt_receipt.items) == 3


def test_receipt_canvas_custom_items_and_currency():
    """Verify custom items, US currency, and grayscale mode."""
    custom_items = [
        {"item": "ORGANIC COFFEE 12OZ", "quantity": 2.0, "unit_price": 8.50},
        {"item": "ALMOND CROISSANT", "quantity": 1.0, "unit_price": 4.25},
    ]
    generator = ReceiptCanvasGenerator(canvas_width=480)
    image, blocks, gt_receipt = generator.generate_receipt(
        merchant="Target",
        store_id="1842",
        receipt_id="RECEIPT #98765",
        receipt_date="2026-03-15 10:15",
        currency="USD",
        items=custom_items,
        tax=1.70,
        tax_label="SALES TAX",
        payment_method="TARJETA",
        mode="L",
    )

    assert image.mode == "L"
    assert image.size[0] == 480
    assert gt_receipt.merchant == "Target"
    assert gt_receipt.currency == "USD"
    assert gt_receipt.subtotal == 21.25  # 2 * 8.50 + 4.25
    assert gt_receipt.tax_total == 1.70
    assert gt_receipt.paid_total == 22.95  # 21.25 + 1.70
    assert gt_receipt.is_balanced is True
    assert len(gt_receipt.items) == 2


def test_bounding_boxes_are_normalized_and_valid():
    """Ensure all ground truth text blocks have normalized coordinates in [0.0, 1.0]."""
    generator = ReceiptCanvasGenerator()
    _, blocks, _ = generator.generate_receipt()

    assert len(blocks) > 10
    for block in blocks:
        assert isinstance(block.bbox, BoundingBox)
        assert 0.0 <= block.bbox.x <= 1.0
        assert 0.0 <= block.bbox.y <= 1.0
        assert 0.0 < block.bbox.width <= 1.0
        assert 0.0 < block.bbox.height <= 1.0
        assert block.bbox.right <= 1.001
        assert block.bbox.bottom <= 1.001
        assert len(block.text) > 0


def test_parser_roundtrip_with_canvas_ground_truth_blocks():
    """Verify that feeding generated blocks into ReceiptParser reconstructs a balanced receipt."""
    generator = ReceiptCanvasGenerator()
    items = [
        {"item": "LECHE LALA ENTERA 1L", "quantity": 1.0, "unit_price": 25.50},
        {"item": "PAN BIMBO BLANCO 680G", "quantity": 1.0, "unit_price": 42.00},
        {"item": "COCA COLA 600ML", "quantity": 1.0, "unit_price": 18.00},
    ]
    _, blocks, gt_receipt = generator.generate_receipt(
        merchant="OXXO",
        store_id="1024",
        receipt_id="FOLIO: 48291",
        receipt_date="2026-03-15",
        currency="MXN",
        items=items,
        tax=0.0,
        payment_method="EFECTIVO",
        payment_amount=100.00,
    )

    parser = ReceiptParser(default_currency="MXN")
    parsed = parser.parse_blocks(blocks)

    assert parsed.merchant == gt_receipt.merchant
    assert parsed.currency == gt_receipt.currency
    assert len(parsed.items) == len(gt_receipt.items)
    assert abs(parsed.subtotal - gt_receipt.subtotal) < 0.01
    assert abs(parsed.paid_total - gt_receipt.paid_total) < 0.01
    assert parsed.is_balanced is True
    assert abs(parsed.balance_delta) < 0.01

    peit_rows = parsed.to_peit_rows()
    assert len(peit_rows) == 3
    for r in peit_rows:
        assert float(r["paid_total"]) < 0


def test_parser_roundtrip_with_tax_and_discount():
    """Verify arithmetic consistency when discount and tax are present."""
    generator = ReceiptCanvasGenerator()
    items = [
        {"item": "LECHE ENTERA 1L", "quantity": 1.0, "unit_price": 25.50},
        {"item": "PAN BLANCO 680G", "quantity": 1.0, "unit_price": 42.00},
    ]
    _, blocks, gt_receipt = generator.generate_receipt(
        merchant="OXXO",
        receipt_id="FOLIO: 12345",
        receipt_date="2026-03-15",
        items=items,
        discount=5.00,
        tax=10.00,
        tax_label="IVA 16%",
    )

    parser = ReceiptParser(default_currency="MXN")
    parsed = parser.parse_blocks(blocks)

    assert parsed.is_balanced is True
    assert abs(parsed.subtotal - 67.50) < 0.01
    assert abs(parsed.discount_total - 5.00) < 0.01
    assert abs(parsed.tax_total - 10.00) < 0.01
    assert abs(parsed.paid_total - 72.50) < 0.01


def test_apply_distortions_preserves_dimensions_and_mode():
    """Test distortion simulator pipeline with rotation, noise, contrast, and vignette."""
    generator = ReceiptCanvasGenerator(canvas_width=400)
    image, _, _ = generator.generate_receipt()
    orig_size = image.size

    # Distortion with RGB mode
    distorted_rgb = apply_distortions(
        image=image,
        rotation_deg=3.0,
        noise_level=0.03,
        fade_contrast=0.80,
        vignette=True,
        seed=101,
    )
    assert distorted_rgb.size == orig_size
    assert distorted_rgb.mode == "RGB"

    # Distortion with Grayscale (L) mode
    gray_img = image.convert("L")
    distorted_gray = apply_distortions(
        image=gray_img,
        rotation_deg=-2.5,
        noise_level=0.02,
        fade_contrast=0.90,
        vignette=True,
        seed=202,
    )
    assert distorted_gray.size == orig_size
    assert distorted_gray.mode == "L"


def test_cli_generate_synthetic_receipt_image(tmp_path: Path):
    """Test profiler CLI helper generate_synthetic_receipt_image."""
    img_path = tmp_path / "test_out_receipt.png"
    manifest_path = tmp_path / "test_out_manifest.json"

    out_file, blocks, receipt = generate_synthetic_receipt_image(
        output_image_path=img_path,
        manifest_path=manifest_path,
        seed=42,
        distort=True,
    )

    assert out_file.exists()
    assert img_path.exists()
    assert manifest_path.exists()

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert "receipt" in manifest_data
    assert "blocks" in manifest_data
    assert manifest_data["receipt"]["merchant"] == "OXXO"
    assert manifest_data["receipt"]["is_balanced"] is True
    assert len(blocks) == len(manifest_data["blocks"])

