"""Bilingual and international heuristic receipt parser for PEIT.

Extracts header metadata (merchant, store ID, date, currency), spatial text
lines, item line candidates (quantity, unit, pack size, price), discounts,
surcharges, taxes, and footer balances from OCR text blocks or raw text lines.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Sequence

from peit.ocr.models import (
    BoundingBox,
    OCRTextBlock,
    ParsedLineItem,
    ParsedReceipt,
)

# Spanish month map
SPANISH_MONTHS = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "sept": 9, "septiembre": 9, "set": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}

# English month map
ENGLISH_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

ALL_MONTHS = {**SPANISH_MONTHS, **ENGLISH_MONTHS}

# Known merchant patterns and their canonical names
KNOWN_MERCHANTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bREAL\s+CANADIAN\s+SUPERSTORE\b|\bSUPERSTORE\b",
     re.IGNORECASE), "Real Canadian Superstore"),
    (re.compile(r"\bSAVE-?ON-?FOODS\b", re.IGNORECASE), "Save-On-Foods"),
    (re.compile(r"\bOXXO\b", re.IGNORECASE), "OXXO"),
    (re.compile(r"\bWALMART\b", re.IGNORECASE), "Walmart"),
    (re.compile(r"\bBODEGA\s+AURRERA\b", re.IGNORECASE), "Bodega Aurrera"),
    (re.compile(r"\bCOSTCO(?:\s+WHOLESALE)?\b", re.IGNORECASE), "Costco"),
    (re.compile(r"\bCHEDRAUI\b", re.IGNORECASE), "Chedraui"),
    (re.compile(r"\bSORIANA\b", re.IGNORECASE), "Soriana"),
    (re.compile(r"\bH-?E-?B\b", re.IGNORECASE), "HEB"),
    (re.compile(r"\bTARGET\b", re.IGNORECASE), "Target"),
    (re.compile(r"\bTRADER\s+JOE'?S\b", re.IGNORECASE), "Trader Joe's"),
    (re.compile(r"\bSEVEN\s+ELEVEN\b|\b7-ELEVEN\b", re.IGNORECASE), "7-Eleven"),
    (re.compile(r"\bFARMACIAS\s+DEL\s+AHORRO\b",
     re.IGNORECASE), "Farmacias del Ahorro"),
    (re.compile(r"\bFARMACIAS\s+GUADALAJARA\b",
     re.IGNORECASE), "Farmacias Guadalajara"),
    (re.compile(r"\bLA\s+COMER\b", re.IGNORECASE), "La Comer"),
    (re.compile(r"\bCITY\s+MARKET\b", re.IGNORECASE), "City Market"),
    (re.compile(r"\bFRESKO\b", re.IGNORECASE), "Fresko"),
    (re.compile(r"\bHOME\s+DEPOT\b", re.IGNORECASE), "The Home Depot"),
    (re.compile(r"\bWHOLE\s+FOODS\b", re.IGNORECASE), "Whole Foods Market"),
    (re.compile(r"\bKROGER\b", re.IGNORECASE), "Kroger"),
]

# Common tax indicators
TAX_KEYWORDS = [
    "iva", "ieps", "tax", "sales tax", "vat", "impuesto", "tasa 16%", "tasa 8%", "tasa 0%",
    "gst", "pst", "hst", "gst 5%", "pst 7%"
]

# Common discount indicators
DISCOUNT_KEYWORDS = [
    "desc", "descuento", "disc", "discount", "ahorro", "bonificacion", "rebaja", "cupon"
]

# Subtotal keywords
SUBTOTAL_KEYWORDS = [
    "subtotal", "sub-total", "sub total"
]

# Paid total / final total keywords
TOTAL_KEYWORDS = [
    "total", "total a pagar", "gran total", "importe total", "paid total", "amount paid",
    "balance due", "monto pagado", "total mxn", "total usd"
]

# Non-item footer / metadata lines to ignore as item candidates
FOOTER_KEYWORDS = [
    "cambio", "change", "efectivo", "cash", "tarjeta", "card", "visa", "mastercard",
    "amex", "american express", "debito", "debit", "credito", "credit",
    "propina", "tip", "gratuity", "puntos", "pago", "tendered", "recibido",
    "cajero", "caja", "articulos", "items sold", "piezas", "ticket", "folio",
    "factura", "rfc", "telefono", "tel:", "gracias por su compra", "thank you",
    "vuelva pronto", "autorizacion", "aprobacion", "cliente", "afiliacion"
]


class ReceiptParser:
  """Heuristic bilingual receipt parser."""

  def __init__(self, default_currency: str = "MXN") -> None:
    self.default_currency = default_currency

  def parse_blocks(self, blocks: list[OCRTextBlock]) -> ParsedReceipt:
    """Parse structured OCR text blocks with 2D spatial baselines."""
    if not blocks:
      return self._create_empty_receipt()

    # Cluster blocks into spatial lines
    lines = self._cluster_blocks_into_lines(blocks)
    # Parse grouped line representations
    return self._parse_from_spatial_lines(lines, blocks)

  def parse_text(self, raw_text: str) -> ParsedReceipt:
    """Fallback line-by-line parser when bounding box coordinates are absent."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
      return self._create_empty_receipt()

    # Generate synthetic blocks/lines
    synthetic_blocks: list[OCRTextBlock] = []
    for i, text in enumerate(lines):
      # 0.0 to 1.0 vertical normalized coordinates
      y = i / max(len(lines), 1)
      h = 1.0 / max(len(lines), 1)
      bbox = BoundingBox(x=0.0, y=y, width=1.0, height=h)
      synthetic_blocks.append(OCRTextBlock(
          text=text, bbox=bbox, confidence=1.0))

    return self.parse_blocks(synthetic_blocks)

  def _cluster_blocks_into_lines(self, blocks: list[OCRTextBlock]) -> list[list[OCRTextBlock]]:
    """Cluster OCR text blocks into logical lines based on vertical overlap."""
    if not blocks:
      return []

    # Sort blocks primarily by y-center, secondarily by x
    sorted_blocks = sorted(blocks, key=lambda b: (b.bbox.center_y, b.bbox.x))

    lines: list[list[OCRTextBlock]] = []
    current_line: list[OCRTextBlock] = [sorted_blocks[0]]

    for block in sorted_blocks[1:]:
      last_block = current_line[-1]
      # Height reference
      ref_height = min(block.bbox.height, last_block.bbox.height)
      if ref_height <= 0:
        ref_height = 0.02  # fallback normalized threshold

      # Compare vertical center distance
      center_diff = abs(block.bbox.center_y - last_block.bbox.center_y)
      threshold = ref_height * 0.65

      if center_diff <= threshold:
        current_line.append(block)
      else:
        # Sort line horizontally left to right
        current_line.sort(key=lambda b: b.bbox.x)
        lines.append(current_line)
        current_line = [block]

    if current_line:
      current_line.sort(key=lambda b: b.bbox.x)
      lines.append(current_line)

    return lines

  def _parse_from_spatial_lines(
      self,
      lines: list[list[OCRTextBlock]],
      all_blocks: list[OCRTextBlock],
  ) -> ParsedReceipt:
    """Extract metadata, line items, taxes, and footer balances from spatial lines."""
    raw_full_text = "\n".join(" ".join(b.text for b in line) for line in lines)
    flat_line_texts = [" ".join(b.text for b in line).strip()
                       for line in lines]

    # 1. Currency Detection
    currency = self._detect_currency(raw_full_text)

    # 2. Date Detection
    receipt_date = self._detect_date(flat_line_texts)

    # 3. Merchant and Store Detection
    merchant, store_id = self._detect_merchant_and_store(flat_line_texts)

    # 4. Receipt ID / Ticket #
    receipt_id = self._detect_receipt_id(
        flat_line_texts, merchant, receipt_date)

    # 5. Extract Totals, Taxes, Discounts from footer
    (
        subtotal,
        discount_total,
        tax_total,
        fee_total,
        deposit_total,
        paid_total,
        footer_start_idx,
    ) = self._extract_financial_totals(flat_line_texts, lines)

    # 6. Extract Line Items (lines before footer)
    item_candidate_lines = lines[:footer_start_idx] if footer_start_idx > 0 else lines
    items = self._extract_line_items(item_candidate_lines)

    # 7. Arithmetic Balancing & Verification
    items_sum = sum(it.total_price for it in items)
    # Expected paid = items_sum - discount_total + tax_total + fee_total + deposit_total
    # If receipt did not detect paid_total explicitly, fallback to items_sum or subtotal
    if paid_total == 0.0:
      if subtotal > 0.0:
        paid_total = subtotal - discount_total + tax_total + fee_total + deposit_total
      else:
        paid_total = items_sum - discount_total + tax_total + fee_total + deposit_total

    if subtotal == 0.0 and items_sum > 0:
      subtotal = items_sum

    calculated_expected_total = items_sum - \
        discount_total + tax_total + fee_total + deposit_total
    balance_delta = round(paid_total - calculated_expected_total, 2)
    is_balanced = abs(balance_delta) < 0.05

    # Overall confidence calculation
    confidence = self._compute_overall_confidence(
        merchant=merchant,
        receipt_date=receipt_date,
        items=items,
        paid_total=paid_total,
        is_balanced=is_balanced,
    )

    return ParsedReceipt(
        receipt_id=receipt_id,
        receipt_date=receipt_date,
        merchant=merchant,
        currency=currency,
        items=items,
        subtotal=round(subtotal, 2),
        discount_total=round(discount_total, 2),
        tax_total=round(tax_total, 2),
        fee_total=round(fee_total, 2),
        deposit_total=round(deposit_total, 2),
        paid_total=round(paid_total, 2),
        is_balanced=is_balanced,
        balance_delta=balance_delta,
        confidence=round(confidence, 3),
        store_id=store_id,
        raw_text=raw_full_text,
    )

  def _detect_currency(self, text: str) -> str:
    """Detect currency code (MXN, USD, EUR, CAD) or fallback to default."""
    upper = text.upper()
    if re.search(r"\b(EUR|€|EUROS)\b", upper):
      return "EUR"
    if re.search(r"\b(CAD|CAD\$|CANADIAN\s+DOLLARS)\b", upper):
      return "CAD"
    if re.search(r"\b(USD|U\.S\.D|US\s*\$)\b", upper):
      return "USD"
    if re.search(r"\b(MXN|M\.N\.|PESOS|MN)\b", upper):
      return "MXN"
    return self.default_currency

  def _detect_date(self, lines: list[str]) -> str:
    """Extract receipt date in YYYY-MM-DD format."""
    # Check first 20 lines and last 10 lines
    target_lines = lines[:20] + lines[-10:]

    for line in target_lines:
      found = self._parse_date_string(line)
      if found:
        return found

    # Fallback to today's ISO date
    return date.today().isoformat()

  def _parse_date_string(self, text: str) -> str | None:
    """Attempt to parse date patterns from text."""
    # 1. YYYY-MM-DD or YYYY/MM/DD
    m = re.search(
        r"\b(20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b", text)
    if m:
      y, month, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
      try:
        return date(y, month, d).isoformat()
      except ValueError:
        pass

    # 2. DD/MM/YYYY or DD-MM-YYYY
    m = re.search(
        r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](20\d{2})\b", text)
    if m:
      d, month, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
      try:
        return date(y, month, d).isoformat()
      except ValueError:
        pass

    # 3. MM/DD/YYYY or MM-DD-YYYY (common in US receipts)
    # We disambiguate: if group 1 > 12, it was DD/MM/YYYY above. If group 2 > 12, it is MM/DD/YYYY:
    m = re.search(
        r"\b(0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])[-/.](20\d{2})\b", text)
    if m:
      month, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
      try:
        return date(y, month, d).isoformat()
      except ValueError:
        pass

    # 4. DD Mon YYYY / DD-Mon-YYYY (e.g. 15 MAR 2026, 15/Mar/2026)
    m = re.search(
        r"\b(0?[1-9]|[12]\d|3[01])\s*(?:de|\s|[-/.])\s*([a-zA-Z]{3,10})\s*(?:de|\s|[-/.])\s*(20\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if m:
      d_str, mon_str, y_str = m.group(1), m.group(2).lower(), m.group(3)
      mon = ALL_MONTHS.get(mon_str) or ALL_MONTHS.get(mon_str[:3])
      if mon:
        try:
          return date(int(y_str), mon, int(d_str)).isoformat()
        except ValueError:
          pass

    # 5. Month DD, YYYY (e.g. March 15, 2026)
    m = re.search(
        r"\b([a-zA-Z]{3,10})\s+(0?[1-9]|[12]\d|3[01]),?\s+(20\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if m:
      mon_str, d_str, y_str = m.group(1).lower(), m.group(2), m.group(3)
      mon = ALL_MONTHS.get(mon_str) or ALL_MONTHS.get(mon_str[:3])
      if mon:
        try:
          return date(int(y_str), mon, int(d_str)).isoformat()
        except ValueError:
          pass

    # 6. DD/MM/YY (2-digit year)
    m = re.search(
        r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](2[0-9])\b", text)
    if m:
      d, month, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
      try:
        return date(y, month, d).isoformat()
      except ValueError:
        pass

    return None

  def _detect_merchant_and_store(self, lines: list[str]) -> tuple[str, str]:
    """Extract merchant name and optional store/branch number."""
    store_id = ""
    # Check store number patterns in top 15 lines
    for line in lines[:15]:
      m = re.search(
          r"(?:#|TIENDA|SUCURSAL|STORE|BRANCH)\s*[:#]?\s*(\d+)", line, re.IGNORECASE)
      if m:
        store_id = m.group(1)
        break

    # Check known merchants
    for line in lines[:10]:
      for pattern, name in KNOWN_MERCHANTS:
        if pattern.search(line):
          return name, store_id

    # Fallback: clean the first non-empty header line
    for line in lines[:5]:
      cleaned = re.sub(r"[#\d]+", "", line).strip()
      # Avoid generic words
      if len(cleaned) >= 3 and not re.search(r"\b(TICKET|BIENVENIDO|WELCOME|FACTURA)\b", cleaned, re.IGNORECASE):
        # Clean up store suffixes
        cleaned = re.split(r"[,;:\-–—]", cleaned)[0].strip()
        return cleaned.title(), store_id

    return "Unknown Merchant", store_id

  def _detect_receipt_id(self, lines: list[str], merchant: str, receipt_date: str) -> str:
    """Find or synthesize a unique receipt identifier."""
    # Look for Ticket / Folio / Receipt / Tran ID in lines
    for line in lines:
      m = re.search(
          r"\b(?:FOLIO|TICKET|RECIBO|RECEIPT|TRANS|TRANSACTION)\s*[:#]?\s*([A-Za-z0-9\-]+)\b",
          line,
          re.IGNORECASE,
      )
      if m:
        val = m.group(1).strip()
        if len(val) >= 3 and not val.lower() in {"de", "para", "en"}:
          return f"rcpt-{val}"

    for line in lines:
      m = re.search(
          r"\b(?:NO\.|REF)\s*[:#]?\s*([A-Za-z0-9\-]+)\b",
          line,
          re.IGNORECASE,
      )
      if m:
        val = m.group(1).strip()
        if len(val) >= 3 and not val.lower() in {"de", "para", "en"}:
          return f"rcpt-{val}"

    # Deterministic synthetic ID
    merch_clean = re.sub(r"[^A-Za-z0-9]", "", merchant).lower()[:8] or "mkt"
    return f"rcpt-{merch_clean}-{receipt_date.replace('-', '')}"

  def _extract_financial_totals(
      self,
      flat_lines: list[str],
      lines: list[list[OCRTextBlock]],
  ) -> tuple[float, float, float, float, float, float, int]:
    """Extract subtotal, discount, tax, fee, deposit, paid_total and footer line index."""
    subtotal = 0.0
    discount_total = 0.0
    tax_total = 0.0
    fee_total = 0.0
    deposit_total = 0.0
    paid_total = 0.0
    footer_start_idx = len(lines)

    # Work backwards from the bottom or scan lines
    for idx, line_text in enumerate(flat_lines):
      lower = line_text.lower()

      # Check if this line marks the beginning of the footer
      is_subtotal_marker = any(k in lower for k in SUBTOTAL_KEYWORDS)
      is_total_marker = any(k in lower for k in TOTAL_KEYWORDS)
      is_tax_marker = any(k in lower for k in TAX_KEYWORDS)
      is_discount_marker = any(k in lower for k in DISCOUNT_KEYWORDS)
      is_fee_marker = any(k in lower for k in ["propina", "tip", "gratuity"])

      # Extract price if present
      price = self._find_trailing_price(line_text)

      # Subtotal
      if is_subtotal_marker and price is not None:
        subtotal = price
        if idx < footer_start_idx:
          footer_start_idx = idx

      # Paid Total
      elif is_total_marker and price is not None:
        # Distinguish from subtotal
        if not is_subtotal_marker:
          paid_total = price
          if idx < footer_start_idx:
            footer_start_idx = idx

      # Taxes
      elif is_tax_marker and price is not None:
        tax_total += price
        if idx < footer_start_idx:
          footer_start_idx = idx

      # Discounts
      elif is_discount_marker and price is not None:
        discount_total += price
        if idx < footer_start_idx:
          footer_start_idx = idx

      # Tip / Gratuity / Propina (fee)
      elif is_fee_marker and price is not None:
        fee_total += price
        if idx < footer_start_idx:
          footer_start_idx = idx

      elif (is_subtotal_marker or is_total_marker) and idx < footer_start_idx:
        footer_start_idx = idx

    return (
        subtotal,
        discount_total,
        tax_total,
        fee_total,
        deposit_total,
        paid_total,
        footer_start_idx,
    )

  def _extract_line_items(self, candidate_lines: list[list[OCRTextBlock]]) -> list[ParsedLineItem]:
    """Extract individual purchased items from candidate text lines."""
    items: list[ParsedLineItem] = []
    i = 0
    n = len(candidate_lines)

    while i < n:
      line_blocks = candidate_lines[i]
      line_text = " ".join(b.text for b in line_blocks).strip()

      if not line_text:
        i += 1
        continue

      # Check if this line is a standalone multi-quantity line (e.g. "3 x 15.00")
      qty_match = self._match_quantity_spec(line_text)
      if qty_match:
        qty, unit_p, unit, pack_size = qty_match
        if items:
          # Update previous item
          prev = items[-1]
          prev.quantity = qty
          prev.unit_price = unit_p
          if unit:
            prev.unit = unit
          if pack_size:
            prev.pack_size = pack_size
          prev.total_price = round(qty * unit_p, 2)
        i += 1
        continue

      # Check if current line contains a price
      parsed_item = self._parse_single_line_item(line_blocks, line_text)
      if parsed_item:
        # Look ahead for quantity or discount line on next line
        if i + 1 < n:
          next_blocks = candidate_lines[i + 1]
          next_text = " ".join(b.text for b in next_blocks).strip()
          next_qty = self._match_quantity_spec(next_text)
          if next_qty:
            qty, unit_p, unit, pack_size = next_qty
            parsed_item.quantity = qty
            parsed_item.unit_price = unit_p
            if unit:
              parsed_item.unit = unit
            if pack_size:
              parsed_item.pack_size = pack_size
            parsed_item.total_price = round(qty * unit_p, 2)
            i += 1  # consumed lookahead

          elif self._is_discount_line(next_text):
            disc_price = self._find_trailing_price(next_text)
            if disc_price:
              parsed_item.discount = disc_price
            i += 1  # consumed discount line

        items.append(parsed_item)
      else:
        # Line without price: could be a standalone item description followed by price or quantity line
        if i + 1 < n:
          next_blocks = candidate_lines[i + 1]
          next_text = " ".join(b.text for b in next_blocks).strip()
          next_qty = self._match_quantity_spec(next_text)
          if next_qty:
            qty, unit_p, unit, pack_size = next_qty
            brand = self._extract_brand(line_text)
            category = self._categorize_item(line_text)
            item_name = self._clean_item_name(line_text)
            if item_name:
              bbox = self._combine_bboxes(line_blocks + next_blocks)
              tot = round(qty * unit_p, 2)
              items.append(
                  ParsedLineItem(
                      item=item_name,
                      brand=brand,
                      category=category,
                      quantity=qty,
                      pack_size=pack_size,
                      unit=unit,
                      unit_price=round(unit_p, 2),
                      total_price=tot,
                      bbox=bbox,
                  )
              )
              i += 2
              continue
      i += 1

    return [it for it in items if it is not None]

  def _parse_single_line_item(
      self,
      blocks: list[OCRTextBlock],
      line_text: str,
  ) -> ParsedLineItem | None:
    """Parse an OCR line into a ParsedLineItem if it has an item description and price."""
    # Check against footer keywords
    lower = line_text.lower()
    if any(k in lower for k in FOOTER_KEYWORDS) or any(k in lower for k in TOTAL_KEYWORDS):
      return None
    if any(k in lower for k in SUBTOTAL_KEYWORDS) or any(k in lower for k in TAX_KEYWORDS):
      return None

    # Check for multi-quantity and price embedded on the same line:
    # e.g.: "2 x 15.00 Milk 30.00" or "Milk 2 x 15.00 30.00" or "LECHE LALA 1L 25.50"
    # 1. Right-aligned price extraction
    price = self._find_trailing_price(line_text)
    if price is None:
      return None

    # Remove trailing price from text to isolate description & inline quantities
    desc_part = self._strip_trailing_price(line_text)
    if not desc_part or len(desc_part.strip()) < 2:
      return None

    # Check for inline quantity: e.g. "3 x 15.00" or "2 @ 12.50" inside desc_part
    qty = 1.0
    unit_price = price
    unit = "ea"
    pack_size = 1.0

    inline_qty = self._match_inline_quantity(desc_part)
    if inline_qty:
      q_val, u_price_val, u_unit, cleaned_desc = inline_qty
      qty = q_val
      unit_price = u_price_val
      if u_unit:
        unit = u_unit
      desc_part = cleaned_desc

    # Extract pack_size / unit from description (e.g. "LECHE 1L", "ARROZ 500G", "WATER 12 PK")
    unit_info = self._extract_pack_unit(desc_part)
    if unit_info:
      pack_size, unit = unit_info

    # Extract brand heuristic
    brand = self._extract_brand(desc_part)

    # Extract category heuristic
    category = self._categorize_item(desc_part)

    # Clean description
    item_name = self._clean_item_name(desc_part)
    if not item_name or len(item_name) < 2:
      return None

    # Bounding box of the entire line
    bbox = self._combine_bboxes(blocks)

    return ParsedLineItem(
        item=item_name,
        brand=brand,
        category=category,
        quantity=qty,
        pack_size=pack_size,
        unit=unit,
        unit_price=round(unit_price, 2),
        total_price=round(price, 2),
        discount=0.0,
        fee=0.0,
        tax=0.0,
        deposit=0.0,
        event_type="one_off",
        store_tier="A",
        store_rating=5.0,
        brand_tier="A",
        brand_rating=5.0,
        product_tier="A",
        product_rating=5.0,
        availability="in_stock",
        notes="",
        confidence=1.0,
        bbox=bbox,
    )

  def _find_trailing_price(self, text: str) -> float | None:
    """Extract a trailing monetary amount from a line of text."""
    # Match standard prices like 25.50, 1,234.50, $12.00, 15.00-
    # Handles European/Mexican formats or trailing tax codes (e.g. 25.50 A, 15.00*)
    m = re.search(
        r"[$€]?\s*([0-9]{1,4}(?:[,\.][0-9]{3})*(?:[\.,][0-9]{2}))\s*[-*A-Za-z]?\s*$", text.strip())
    if m:
      raw_num = m.group(1).replace(",", "")
      try:
        val = float(raw_num)
        return val
      except ValueError:
        pass

    # Fallback for integer prices like $25 or 25
    m_int = re.search(r"[$€]\s*([0-9]+(?:\.[0-9]{1,2})?)\s*$", text.strip())
    if m_int:
      try:
        return float(m_int.group(1))
      except ValueError:
        pass

    return None

  def _strip_trailing_price(self, text: str) -> str:
    """Strip trailing price from a line to keep the item description."""
    text = text.strip()
    text = re.sub(
        r"[$€]?\s*[0-9]{1,4}(?:[,\.][0-9]{3})*(?:[\.,][0-9]{2})\s*[-*A-Za-z]?\s*$", "", text)
    text = re.sub(r"[$€]\s*[0-9]+(?:\.[0-9]{1,2})?\s*$", "", text)
    return text.strip()

  def _match_quantity_spec(self, text: str) -> tuple[float, float, str, float] | None:
    """Match quantity line such as '2 x 25.50', '2 @ $12.00', '1.500 kg x 45.00/kg'."""
    # 1.500 kg x 45.00
    m = re.search(
        r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\s*(?:x|@|\*)\s*[$€]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/([a-zA-Z]+))?",
        text,
        re.IGNORECASE,
    )
    if m:
      qty = float(m.group(1))
      unit = m.group(2) or m.group(4) or "ea"
      unit_price = float(m.group(3))
      return qty, unit_price, unit.lower(), 1.0

    # Pattern: "CANT: 2 P.U. $15.00"
    m2 = re.search(
        r"CANT(?:IDAD)?\s*[:#]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:P\.U\.?|PRECIO)?\s*[:$€]?\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE,
    )
    if m2:
      return float(m2.group(1)), float(m2.group(2)), "ea", 1.0

    return None

  def _match_inline_quantity(self, text: str) -> tuple[float, float, str, str] | None:
    """Match inline quantity spec like '2 x 15.00' inside text and return remainder."""
    m = re.search(
        r"(.*?)\s+([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\s*(?:x|@|\*)\s*[$€]?\s*([0-9]+(?:\.[0-9]+)?)\s*(.*)",
        text,
        re.IGNORECASE,
    )
    if m:
      pre, qty_s, unit_s, uprice_s, post = m.group(
          1), m.group(2), m.group(3), m.group(4), m.group(5)
      cleaned = f"{pre} {post}".strip()
      qty = float(qty_s)
      uprice = float(uprice_s)
      unit = (unit_s or "ea").lower()
      return qty, uprice, unit, cleaned
    return None

  def _is_discount_line(self, text: str) -> bool:
    """Check if line is a discount line following an item."""
    lower = text.lower()
    return any(k in lower for k in DISCOUNT_KEYWORDS)

  def _extract_pack_unit(self, text: str) -> tuple[float, str] | None:
    """Extract pack size and unit (e.g. 1L, 500g, 250 ml, 12 pk, 6 pack)."""
    m = re.search(
        r"\b([0-9]+(?:\.[0-9]+)?)\s*(ml|l|lt|g|kg|oz|lb|pk|pack|pzas?|pz)\b", text, re.IGNORECASE)
    if m:
      val = float(m.group(1))
      unit = m.group(2).lower()
      if unit in {"lt", "l"}:
        return val, "L"
      if unit in {"ml"}:
        return val, "ml"
      if unit in {"kg"}:
        return val, "kg"
      if unit in {"g"}:
        return val, "g"
      if unit in {"pk", "pack", "pza", "pzas", "pz"}:
        return val, "ea"
      return val, unit
    return None

  def _extract_brand(self, text: str) -> str:
    """Extract recognizable brand names or return 'Generic'."""
    upper = text.upper()
    known_brands = [
        "LALA", "ALPURA", "BIMBO", "COCA COLA", "COCA-COLA", "PEPSI",
        "SABRITAS", "BARCEL", "MARINELA", "GAMESA", "NESTLE", "KELLOGG'S",
        "KIRKLAND", "GREAT VALUE", "MEMBER'S MARK", "VALE", "SANTA CLARA",
        "SIGMA", "SAN RAFAEL", "FUD", "YOPLAIT", "DANONE", "HERDEZ", "DEL MONTE",
        "TRADER JOE'S", "365", "HEINZ", "KRAFT", "COLGATE", "CREST", "PALMOLIVE"
    ]
    for b in known_brands:
      if re.search(r"\b" + re.escape(b) + r"\b", upper):
        return b.title()
    return "Generic"

  def _categorize_item(self, text: str) -> str:
    """Assign an expenditure category heuristic."""
    lower = text.lower()
    if any(w in lower for w in ["leche", "milk", "queso", "cheese", "pan", "bread", "huevo", "egg", "arroz", "rice", "frijol", "cereal", "cafe", "coffee", "te", "tea", "agua", "water", "jugo", "juice", "soda", "coca", "refresco", "manzana", "apple", "platano", "banana", "tomate", "aguacate", "carne", "meat", "pollo", "chicken", "pescado", "fish", "yogurt", "galletas"]):
      return "Food and beverages"
    if any(w in lower for w in ["jabon", "soap", "shampoo", "pasta dental", "toothpaste", "papel", "detergente", "cloro", "limpiador", "desodorante"]):
      return "Household and personal care"
    if any(w in lower for w in ["farmacia", "medicina", "aspirina", "paracetamol", "curitas", "alcohol"]):
      return "Health and medical"
    if any(w in lower for w in ["gasolina", "gas", "estacionamiento", "parking", "peaje", "uber", "transporte"]):
      return "Transportation"
    return "General"

  def _clean_item_name(self, text: str) -> str:
    """Clean redundant codes, barcodes, and characters from item name."""
    # Remove initial barcodes or SKU numbers
    text = re.sub(r"^[0-9]{5,14}\s+", "", text.strip())
    # Clean extra punctuation
    text = re.sub(r"[*#_=+]", " ", text)
    return " ".join(text.split()).strip()

  def _combine_bboxes(self, blocks: list[OCRTextBlock]) -> BoundingBox | None:
    """Compute the enclosing bounding box for a set of text blocks."""
    if not blocks:
      return None
    min_x = min(b.bbox.x for b in blocks)
    min_y = min(b.bbox.y for b in blocks)
    max_r = max(b.bbox.right for b in blocks)
    max_b = max(b.bbox.bottom for b in blocks)
    return BoundingBox(x=min_x, y=min_y, width=max_r - min_x, height=max_b - min_y)

  def _compute_overall_confidence(
      self,
      merchant: str,
      receipt_date: str,
      items: list[ParsedLineItem],
      paid_total: float,
      is_balanced: bool,
  ) -> float:
    """Compute overall receipt extraction confidence score [0.0, 1.0]."""
    score = 0.0
    # Merchant detected
    if merchant != "Unknown Merchant":
      score += 0.25
    else:
      score += 0.10

    # Valid date
    if receipt_date:
      score += 0.20

    # Items extracted
    if items:
      score += 0.25
      # High-confidence items
      avg_item_conf = sum(it.confidence for it in items) / len(items)
      score += 0.10 * avg_item_conf

    # Arithmetic balancing
    if is_balanced:
      score += 0.20
    elif paid_total > 0:
      score += 0.10

    return min(score, 1.0)

  def _create_empty_receipt(self) -> ParsedReceipt:
    """Create empty ParsedReceipt when no text is detected."""
    return ParsedReceipt(
        receipt_id="rcpt-unknown",
        receipt_date=date.today().isoformat(),
        merchant="Unknown Merchant",
        currency=self.default_currency,
        items=[],
        confidence=0.0,
    )
