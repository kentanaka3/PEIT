"""Econometric and Computer Vision benchmark evaluation harness for PEIT OCR.

Evaluates OCR and heuristic parser performance against ground truth annotations:
- Character Error Rate (CER) via normalized edit distance.
- Word Error Rate (WER) via token-level edit distance.
- Bipartite matching for line item extraction (Precision, Recall, F1 score).
- Arithmetic balancing pass rate conforming to PEIT double-entry / ledger integrity.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageOps

from peit.ocr.models import (
    BoundingBox,
    OCRTextBlock,
    ParsedLineItem,
    ParsedReceipt,
)
from peit.ocr.parser import ReceiptParser


def levenshtein_distance(seq1: Sequence[Any], seq2: Sequence[Any]) -> int:
  """Compute standard Levenshtein edit distance between two sequences.

  Supports characters (strings) or token sequences (words).
  Calculates minimum insertions, deletions, and substitutions.
  """
  m, n = len(seq1), len(seq2)
  if m == 0:
    return n
  if n == 0:
    return m

  dp = list(range(n + 1))
  for i in range(1, m + 1):
    prev = dp[0]
    dp[0] = i
    for j in range(1, n + 1):
      temp = dp[j]
      cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
      dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
      prev = temp

  return dp[n]


@dataclass
class BenchmarkMetrics:
  """Aggregated benchmark evaluation metrics across a dataset of receipts.

  Attributes:
      cer: Character Error Rate (Levenshtein distance / max(1, len(reference))).
      wer: Word Error Rate (Word-level Levenshtein distance / max(1, words(reference))).
      line_item_precision: True positive line items / total predicted line items.
      line_item_recall: True positive line items / total ground truth line items.
      line_item_f1: Harmonic mean of precision and recall.
      balance_pass_rate: Fraction of receipts whose calculated balance matches paid total.
      total_receipts: Number of evaluated receipt images/documents.
      receipt_results: Detailed per-receipt evaluation metrics and matched items.
  """

  cer: float
  wer: float
  line_item_precision: float
  line_item_recall: float
  line_item_f1: float
  balance_pass_rate: float
  total_receipts: int
  receipt_results: list[dict[str, Any]] = field(default_factory=list)

  def summary(self) -> str:
    """Format metrics as a human-readable tabular summary."""
    lines = [
        "=" * 60,
        "PEIT OCR & RECEIPT PARSER BENCHMARK RESULTS",
        "=" * 60,
        f"Total Receipts Evaluated: {self.total_receipts}",
        f"Character Error Rate (CER): {self.cer:.2%}",
        f"Word Error Rate (WER):      {self.wer:.2%}",
        f"Line Item Precision:        {self.line_item_precision:.2%}",
        f"Line Item Recall:           {self.line_item_recall:.2%}",
        f"Line Item F1 Score:         {self.line_item_f1:.2%}",
        f"Balance Pass Rate:          {self.balance_pass_rate:.2%}",
        "=" * 60,
    ]
    return "\n".join(lines)


class ReceiptBenchmarkRunner:
  """Benchmark evaluation runner comparing parsed receipts against ground-truth annotations."""

  def __init__(
      self,
      name_similarity_threshold: float = 0.80,
      price_diff_threshold: float = 0.02,
      balance_tolerance: float = 0.01,
  ) -> None:
    """Initialize receipt benchmark runner with matching tolerances.

    Args:
        name_similarity_threshold: Minimum string similarity ratio for line item names.
        price_diff_threshold: Maximum absolute price discrepancy for line item match.
        balance_tolerance: Maximum arithmetic imbalance delta allowed for balance pass.
    """
    self.name_similarity_threshold = name_similarity_threshold
    self.price_diff_threshold = price_diff_threshold
    self.balance_tolerance = balance_tolerance

  @staticmethod
  def compute_cer(reference: str, hypothesis: str) -> float:
    """Compute Character Error Rate (CER) between reference and hypothesis strings.

    Formula: edit_distance(ref, hyp) / max(1, len(ref))
    """
    if not reference:
      return 0.0 if not hypothesis else 1.0
    dist = levenshtein_distance(reference, hypothesis)
    return dist / len(reference)

  @staticmethod
  def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate (WER) between reference and hypothesis text.

    Formula: token_edit_distance(ref_tokens, hyp_tokens) / max(1, len(ref_tokens))
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
      return 0.0 if not hyp_words else 1.0
    dist = levenshtein_distance(ref_words, hyp_words)
    return dist / len(ref_words)

  def evaluate_predictions(
      self,
      ground_truth: ParsedReceipt,
      predicted: ParsedReceipt,
  ) -> dict[str, Any]:
    """Evaluate predicted receipt parsing against ground truth.

    Performs greedy maximum-weight bipartite matching of line items:
    Two items match (True Positive) if:
    1. String similarity ratio >= name_similarity_threshold (default 0.80).
    2. Absolute price difference <= price_diff_threshold (default $0.02).

    Computes precision, recall, F1, balance check, and CER/WER.

    Args:
        ground_truth: Ground truth ParsedReceipt.
        predicted: Predicted ParsedReceipt.

    Returns:
        Dictionary containing evaluation metrics and match details.
    """
    gt_items = ground_truth.items
    pred_items = predicted.items

    # Generate candidates for bipartite matching: (score, gt_idx, pred_idx)
    candidates: list[tuple[float, int, int]] = []
    for g_idx, g_item in enumerate(gt_items):
      for p_idx, p_item in enumerate(pred_items):
        # String similarity
        name_sim = difflib.SequenceMatcher(
            None,
            g_item.item.strip().upper(),
            p_item.item.strip().upper(),
        ).ratio()

        price_diff = abs(g_item.total_price - p_item.total_price)

        if name_sim >= self.name_similarity_threshold and price_diff <= self.price_diff_threshold:
          # Score combines name similarity and price closeness
          score = name_sim - (price_diff * 0.1)
          candidates.append((score, g_idx, p_idx))

    # Sort descending by score
    candidates.sort(key=lambda x: x[0], reverse=True)

    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    matched_pairs: list[tuple[int, int]] = []

    for score, g_idx, p_idx in candidates:
      if g_idx not in matched_gt and p_idx not in matched_pred:
        matched_gt.add(g_idx)
        matched_pred.add(p_idx)
        matched_pairs.append((g_idx, p_idx))

    tp = len(matched_pairs)
    fp = len(pred_items) - tp
    fn = len(gt_items) - tp

    precision = tp / \
        len(pred_items) if pred_items else (1.0 if not gt_items else 0.0)
    recall = tp / len(gt_items) if gt_items else 1.0
    f1 = (2.0 * precision * recall / (precision + recall)
          ) if (precision + recall) > 0 else 0.0

    # Balance verification
    # An arithmetic pass occurs if predicted is balanced within tolerance
    pred_expected = (
        sum(it.total_price for it in pred_items)
        - predicted.discount_total
        + predicted.tax_total
        + predicted.fee_total
        + predicted.deposit_total
    )
    balance_discrepancy = abs(predicted.paid_total - pred_expected)
    balance_pass = balance_discrepancy <= self.balance_tolerance

    # CER / WER comparison between raw_text if present, or serialized representation
    gt_text = ground_truth.raw_text or "\n".join(it.item for it in gt_items)
    pred_text = predicted.raw_text or "\n".join(it.item for it in pred_items)

    cer = self.compute_cer(gt_text, pred_text) if gt_text else 0.0
    wer = self.compute_wer(gt_text, pred_text) if gt_text else 0.0

    return {
        "receipt_id": ground_truth.receipt_id,
        "merchant_gt": ground_truth.merchant,
        "merchant_pred": predicted.merchant,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "balance_pass": balance_pass,
        "balance_discrepancy": balance_discrepancy,
        "cer": cer,
        "wer": wer,
        "matched_pairs_count": tp,
    }

  def load_ground_truth(self, truth_path: Path | str) -> tuple[ParsedReceipt, list[OCRTextBlock], str]:
    """Load ground truth JSON annotation and reconstruct ParsedReceipt and OCRTextBlock models.

    Args:
        truth_path: Path to `*_truth.json` file.

    Returns:
        Tuple of (ParsedReceipt, list[OCRTextBlock], image_filename).
    """
    truth_p = Path(truth_path)
    with open(truth_p, "r", encoding="utf-8") as f:
      data = json.load(f)

    meta = data.get("receipt_metadata", {})
    line_items_data = data.get("line_items", [])
    text_blocks_data = data.get("text_blocks", [])
    image_file = data.get("image_file", "")

    parsed_items: list[ParsedLineItem] = []
    for it in line_items_data:
      parsed_items.append(
          ParsedLineItem(
              item=it.get("item", ""),
              brand=it.get("brand", "Generic"),
              category=it.get("category", "General"),
              quantity=float(it.get("quantity", 1.0)),
              pack_size=float(it.get("pack_size", 1.0)),
              unit=it.get("unit", "ea"),
              unit_price=float(it.get("unit_price", 0.0)),
              total_price=float(it.get("total_price", 0.0)),
              discount=float(it.get("discount", 0.0)),
              fee=float(it.get("fee", 0.0)),
              tax=float(it.get("tax", 0.0)),
              deposit=float(it.get("deposit", 0.0)),
              availability=it.get("availability", "in_stock"),
          )
      )

    text_blocks: list[OCRTextBlock] = []
    for tb in text_blocks_data:
      bbox_dict = tb.get("bbox", {})
      bbox = BoundingBox(
          x=float(bbox_dict.get("x", 0.0)),
          y=float(bbox_dict.get("y", 0.0)),
          width=float(bbox_dict.get("width", 0.0)),
          height=float(bbox_dict.get("height", 0.0)),
      )
      text_blocks.append(
          OCRTextBlock(
              text=tb.get("text", ""),
              bbox=bbox,
              confidence=float(tb.get("confidence", 1.0)),
          )
      )

    raw_text = "\n".join(b.text for b in text_blocks)

    receipt = ParsedReceipt(
        receipt_id=meta.get("receipt_id", f"rcpt-{truth_p.stem}"),
        receipt_date=meta.get("receipt_date", ""),
        merchant=meta.get("merchant", "Unknown Merchant"),
        currency=meta.get("currency", "CAD"),
        items=parsed_items,
        subtotal=float(meta.get("subtotal", 0.0)),
        discount_total=float(meta.get("discount_total", 0.0)),
        tax_total=float(meta.get("tax_total", 0.0)),
        fee_total=float(meta.get("fee_total", 0.0)),
        deposit_total=float(meta.get("deposit_total", 0.0)),
        paid_total=float(meta.get("paid_total", 0.0)),
        is_balanced=True,
        raw_text=raw_text,
    )

    return receipt, text_blocks, image_file

  def run_benchmark(
      self,
      receipts_dir: Path | str,
      parser: ReceiptParser | None = None,
  ) -> BenchmarkMetrics:
    """Run benchmark evaluation over directory of ground truth annotations and images.

    For each `*_truth.json` in `receipts_dir`:
    1. Loads ground truth annotation, line items, and representative text blocks.
    2. Validates image EXIF orientation (handles EXIF orientation = 6 via `ImageOps.exif_transpose`).
    3. Parses representative text blocks or raw text using `ReceiptParser`.
    4. Computes per-receipt metrics (Precision, Recall, F1, CER, WER, Balance Pass).
    5. Aggregates metrics across the dataset into `BenchmarkMetrics`.

    Args:
        receipts_dir: Directory containing receipt images and `*_truth.json` files.
        parser: ReceiptParser instance. Defaults to new `ReceiptParser(default_currency='CAD')`.

    Returns:
        Aggregated `BenchmarkMetrics`.
    """
    dir_path = Path(receipts_dir)
    if parser is None:
      parser = ReceiptParser(default_currency="CAD")

    truth_files = sorted(dir_path.glob("*_truth.json"))
    if not truth_files:
      return BenchmarkMetrics(
          cer=0.0,
          wer=0.0,
          line_item_precision=0.0,
          line_item_recall=0.0,
          line_item_f1=0.0,
          balance_pass_rate=0.0,
          total_receipts=0,
          receipt_results=[],
      )

    results: list[dict[str, Any]] = []

    for truth_file in truth_files:
      gt_receipt, text_blocks, image_file = self.load_ground_truth(truth_file)

      # Inspect corresponding image if exists and verify EXIF handling
      img_path = dir_path / image_file if image_file else dir_path / \
          (truth_file.stem.replace("_truth", "") + ".jpg")
      if img_path.exists():
        with Image.open(img_path) as img:
          # Test orientation transposition safely
          transposed = ImageOps.exif_transpose(img)
          assert transposed.size[0] <= transposed.size[1], "Transposed image should be portrait oriented"

      # Parse using the benchmarked parser
      if text_blocks:
        predicted_receipt = parser.parse_blocks(text_blocks)
      else:
        predicted_receipt = parser.parse_text(gt_receipt.raw_text)

      eval_res = self.evaluate_predictions(gt_receipt, predicted_receipt)
      results.append(eval_res)

    total = len(results)
    avg_cer = sum(r["cer"] for r in results) / total if total > 0 else 0.0
    avg_wer = sum(r["wer"] for r in results) / total if total > 0 else 0.0
    avg_precision = sum(r["precision"]
                        for r in results) / total if total > 0 else 0.0
    avg_recall = sum(r["recall"]
                     for r in results) / total if total > 0 else 0.0
    avg_f1 = sum(r["f1"] for r in results) / total if total > 0 else 0.0
    balance_passes = sum(1 for r in results if r["balance_pass"])
    balance_rate = balance_passes / total if total > 0 else 0.0

    return BenchmarkMetrics(
        cer=round(avg_cer, 4),
        wer=round(avg_wer, 4),
        line_item_precision=round(avg_precision, 4),
        line_item_recall=round(avg_recall, 4),
        line_item_f1=round(avg_f1, 4),
        balance_pass_rate=round(balance_rate, 4),
        total_receipts=total,
        receipt_results=results,
    )
