"""Optical Character Recognition (OCR) and receipt parsing prototype for PEIT.

Provides spatial block alignment, bilingual heuristic extraction (ES/EN),
financial balance verification, and lossless conversion to 25-column PEIT
ledger rows.
"""

from __future__ import annotations

from peit.ocr.benchmark import (
    BenchmarkMetrics,
    ReceiptBenchmarkRunner,
    levenshtein_distance,
)
from peit.ocr.canvas import ReceiptCanvasGenerator, apply_distortions
from peit.ocr.models import (
    BoundingBox,
    OCRTextBlock,
    ParsedLineItem,
    ParsedReceipt,
)
from peit.ocr.parser import ReceiptParser

__all__ = [
    "BenchmarkMetrics",
    "BoundingBox",
    "OCRTextBlock",
    "ParsedLineItem",
    "ParsedReceipt",
    "ReceiptBenchmarkRunner",
    "ReceiptCanvasGenerator",
    "ReceiptParser",
    "apply_distortions",
    "levenshtein_distance",
]
