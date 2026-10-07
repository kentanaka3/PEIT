"""Tests for Milestone 4C: Real Receipt Photo Benchmark Suite and Evaluation Harness."""

from __future__ import annotations

from pathlib import Path
import pytest

from peit.ocr.benchmark import (
    BenchmarkMetrics,
    ReceiptBenchmarkRunner,
    levenshtein_distance,
)
from peit.ocr.models import (
    BoundingBox,
    OCRTextBlock,
    ParsedLineItem,
    ParsedReceipt,
)
from peit.ocr.parser import ReceiptParser


def test_levenshtein_distance():
    """Verify sequence and character level edit distances."""
    assert levenshtein_distance("", "") == 0
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("hello", "hello") == 0
    assert levenshtein_distance("apple", "apples") == 1
    assert levenshtein_distance("abc", "") == 3
    assert levenshtein_distance("", "def") == 3

    # Token list
    assert levenshtein_distance(["milk", "bread"], ["milk", "bread"]) == 0
    assert levenshtein_distance(["milk", "bread"], ["milk", "cheese", "bread"]) == 1
    assert levenshtein_distance(["milk", "eggs"], ["beer"]) == 2


def test_compute_cer_and_wer():
    """Verify CER and WER computation on known string pairs."""
    runner = ReceiptBenchmarkRunner()

    # Exact match
    assert runner.compute_cer("COSTCO WHOLESALE", "COSTCO WHOLESALE") == 0.0
    assert runner.compute_wer("COSTCO WHOLESALE", "COSTCO WHOLESALE") == 0.0

    # Insertion
    # "ABC" -> "ABCD" (1 insertion / 3 len = 0.3333...)
    assert pytest.approx(runner.compute_cer("ABC", "ABCD"), rel=1e-3) == 1.0 / 3.0
    assert pytest.approx(runner.compute_wer("ORGANIC MILK", "ORGANIC WHOLE MILK"), rel=1e-3) == 1.0 / 2.0

    # Deletion
    # "ABC" -> "AB" (1 deletion / 3 len = 0.3333...)
    assert pytest.approx(runner.compute_cer("ABC", "AB"), rel=1e-3) == 1.0 / 3.0
    assert pytest.approx(runner.compute_wer("A B C", "A C"), rel=1e-3) == 1.0 / 3.0

    # Substitution
    # "CAT" -> "BAT" (1 sub / 3 len = 0.3333...)
    assert pytest.approx(runner.compute_cer("CAT", "BAT"), rel=1e-3) == 1.0 / 3.0
    assert pytest.approx(runner.compute_wer("BUY APPLES TODAY", "BUY ORANGES TODAY"), rel=1e-3) == 1.0 / 3.0

    # Empty edge cases
    assert runner.compute_cer("", "") == 0.0
    assert runner.compute_wer("", "") == 0.0
    assert runner.compute_cer("", "SOMETHING") == 1.0
    assert runner.compute_wer("", "SOMETHING") == 1.0


def test_evaluate_predictions_perfect_match():
    """Verify evaluate_predictions on identical ground truth and predicted receipts."""
    items = [
        ParsedLineItem(item="LECHE LALA 1L", total_price=25.50, unit_price=25.50),
        ParsedLineItem(item="PAN BIMBO 680G", total_price=42.00, unit_price=42.00),
    ]
    gt = ParsedReceipt(
        receipt_id="rcpt-001",
        receipt_date="2026-03-15",
        merchant="OXXO",
        currency="MXN",
        items=items,
        subtotal=67.50,
        paid_total=67.50,
        is_balanced=True,
    )
    pred = ParsedReceipt(
        receipt_id="rcpt-001",
        receipt_date="2026-03-15",
        merchant="OXXO",
        currency="MXN",
        items=[
            ParsedLineItem(item="LECHE LALA 1L", total_price=25.50, unit_price=25.50),
            ParsedLineItem(item="PAN BIMBO 680G", total_price=42.00, unit_price=42.00),
        ],
        subtotal=67.50,
        paid_total=67.50,
        is_balanced=True,
    )

    runner = ReceiptBenchmarkRunner()
    result = runner.evaluate_predictions(gt, pred)

    assert result["tp"] == 2
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0
    assert result["balance_pass"] is True
    assert result["balance_discrepancy"] == 0.0


def test_evaluate_predictions_partial_match():
    """Verify bipartite matching with slight character typos, missing items, and arithmetic imbalance."""
    gt_items = [
        ParsedLineItem(item="ORGANIC MILK 1 GAL", total_price=4.99),
        ParsedLineItem(item="WHEAT BREAD", total_price=2.50),
        ParsedLineItem(item="GALA APPLES 1 LB", total_price=1.99),
    ]
    gt = ParsedReceipt(
        receipt_id="rcpt-002",
        receipt_date="2026-03-15",
        merchant="Trader Joe's",
        currency="USD",
        items=gt_items,
        subtotal=9.48,
        paid_total=9.48,
    )

    # Predicted has 1 typo (ORGANIC MILK 1 GAL -> ORGANIC MILK 1GAL, similarity > 0.90),
    # 1 extra false positive item, and misses GALA APPLES
    pred_items = [
        ParsedLineItem(item="ORGANIC MILK 1GAL", total_price=4.99),
        ParsedLineItem(item="WHEAT BREAD", total_price=2.50),
        ParsedLineItem(item="CHOCOLATE BAR", total_price=3.00),  # FP
    ]
    pred = ParsedReceipt(
        receipt_id="rcpt-002",
        receipt_date="2026-03-15",
        merchant="Trader Joe's",
        currency="USD",
        items=pred_items,
        subtotal=10.49,
        paid_total=9.48,  # Does not match sum (10.49), imbalance delta = 1.01
    )

    runner = ReceiptBenchmarkRunner()
    res = runner.evaluate_predictions(gt, pred)

    assert res["tp"] == 2  # milk and bread matched
    assert res["fp"] == 1  # chocolate bar
    assert res["fn"] == 1  # apples missing
    assert pytest.approx(res["precision"], rel=1e-3) == 2.0 / 3.0
    assert pytest.approx(res["recall"], rel=1e-3) == 2.0 / 3.0
    assert pytest.approx(res["f1"], rel=1e-3) == 2.0 / 3.0
    assert res["balance_pass"] is False
    assert pytest.approx(res["balance_discrepancy"], rel=1e-3) == 1.01


def test_load_ground_truth():
    """Verify loading and parsing ground truth JSON files."""
    runner = ReceiptBenchmarkRunner()
    truth_path = Path("test/data/receipts/20261006_221633_truth.json")
    receipt, text_blocks, image_file = runner.load_ground_truth(truth_path)

    assert receipt.receipt_id == "rcpt-220255"
    assert receipt.merchant == "Real Canadian Superstore"
    assert receipt.currency == "CAD"
    assert len(receipt.items) == 3
    assert len(text_blocks) == 12
    assert image_file == "20261006_221633.jpg"

    # Verify rows generation
    rows = receipt.to_peit_rows()
    assert len(rows) == 3


def test_run_benchmark_dataset():
    """Verify benchmark run across the real smartphone receipt dataset."""
    runner = ReceiptBenchmarkRunner()
    parser = ReceiptParser(default_currency="CAD")
    receipts_dir = Path("test/data/receipts")

    metrics = runner.run_benchmark(receipts_dir=receipts_dir, parser=parser)

    assert metrics.total_receipts == 6
    assert isinstance(metrics.cer, float)
    assert isinstance(metrics.wer, float)
    assert metrics.line_item_f1 > 0.70
    assert metrics.line_item_precision > 0.75
    assert metrics.line_item_recall > 0.70
    assert metrics.balance_pass_rate >= 0.50

    # Ensure summary string formats correctly
    summary = metrics.summary()
    assert "BENCHMARK RESULTS" in summary
    assert "Total Receipts Evaluated: 6" in summary

