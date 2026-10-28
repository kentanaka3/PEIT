"""Synthetic receipt image canvas generator and photometric distortion simulator.

Renders realistic thermal receipt images onto PIL canvases with pixel and
normalized bounding box tracking, ground-truth metadata preservation, and
photometric/geometric distortion pipelines simulating smartphone captures.
"""

from __future__ import annotations

import math
import random
from typing import Any, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont

from peit.ocr.models import (
    BoundingBox,
    OCRTextBlock,
    ParsedLineItem,
    ParsedReceipt,
)


class ReceiptCanvasGenerator:
    """Renders thermal receipt images and tracks ground truth OCR text blocks.

    Generates realistic 1-bit / 8-bit / RGB thermal receipt images from
    either PEIT structured data models, synthetic generator manifests, or
    custom specifications. Tracks 2D bounding boxes at both word and line levels.
    """

    def __init__(
        self,
        canvas_width: int = 540,
        margin_x: int = 28,
        margin_top: int = 36,
        margin_bottom: int = 40,
        line_height: int = 24,
        bg_color: tuple[int, int, int] = (252, 252, 250),
        text_color: tuple[int, int, int] = (24, 24, 24),
        font: ImageFont.ImageFont | None = None,
    ) -> None:
        """Initialize receipt canvas generator.

        Args:
            canvas_width: Width of receipt image canvas in pixels.
            margin_x: Horizontal margin in pixels.
            margin_top: Top margin in pixels.
            margin_bottom: Bottom margin in pixels.
            line_height: Default line spacing in pixels.
            bg_color: Background paper RGB tuple.
            text_color: Thermal ink RGB tuple.
            font: Optional PIL ImageFont instance. If None, default font is used.
        """
        self.canvas_width = canvas_width
        self.margin_x = margin_x
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
        self.line_height = line_height
        self.bg_color = bg_color
        self.text_color = text_color
        self.font = font or ImageFont.load_default()

    def generate_receipt(
        self,
        merchant: str = "OXXO",
        store_id: str = "1024",
        address: str = "AV. REFORMA #1024, CDMX",
        receipt_id: str = "FOLIO: 48291",
        receipt_date: str = "2026-03-15 14:32",
        currency: str = "MXN",
        items: Sequence[dict[str, Any]] | None = None,
        subtotal: float | None = None,
        discount: float = 0.0,
        tax: float = 0.0,
        tax_label: str = "IVA 16%",
        fee: float = 0.0,
        deposit: float = 0.0,
        payment_method: str = "EFECTIVO",
        payment_amount: float | None = None,
        footer_message: str = "GRACIAS POR SU COMPRA",
        mode: str = "RGB",
    ) -> tuple[Image.Image, list[OCRTextBlock], ParsedReceipt]:
        """Generate a complete synthetic receipt image with ground-truth OCR text blocks.

        Args:
            merchant: Store or business name (e.g. 'OXXO', 'Walmart', 'Target').
            store_id: Store branch or store number identifier.
            address: Store location or address line.
            receipt_id: Receipt reference or ticket ID (e.g. 'FOLIO: 48291').
            receipt_date: Timestamp string or ISO date.
            currency: Currency code ('MXN', 'USD', etc.).
            items: List of item dictionaries with keys:
                   'item' (str), 'unit_price' (float), optional 'quantity' (float),
                   'pack_size' (float), 'unit' (str), 'discount' (float).
            subtotal: Optional subtotal. If None, calculated from sum of items.
            discount: Total receipt discount.
            tax: Total tax amount.
            tax_label: Label for tax line ('IVA 16%', 'SALES TAX', etc.).
            fee: Additional fees or tip.
            deposit: Bottle or container deposits.
            payment_method: Tender method ('EFECTIVO', 'TARJETA', 'CASH', etc.).
            payment_amount: Amount tendered by customer.
            footer_message: Closing marketing or courtesy message.
            mode: Color mode of resulting PIL image ('RGB' or 'L').

        Returns:
            Tuple of (rendered_image, ground_truth_blocks, ground_truth_receipt).
        """
        # Default sample items if none provided
        if items is None:
            if currency.upper() == "USD":
                items = [
                    {"item": "ORGANIC MILK 1 GAL", "quantity": 1.0, "unit_price": 4.99},
                    {"item": "WHEAT BREAD", "quantity": 1.0, "unit_price": 2.50},
                    {"item": "APPLES 1 LB", "quantity": 1.0, "unit_price": 1.99},
                ]
            else:
                items = [
                    {"item": "LECHE LALA ENTERA 1L", "quantity": 1.0, "unit_price": 25.50},
                    {"item": "PAN BIMBO BLANCO 680G", "quantity": 1.0, "unit_price": 42.00},
                    {"item": "COCA COLA 600ML", "quantity": 1.0, "unit_price": 18.00},
                ]

        # Calculate line item totals and build ParsedLineItem models
        parsed_items: list[ParsedLineItem] = []
        calc_subtotal = 0.0
        for it in items:
            name = str(it.get("item", "ITEM"))
            qty = float(it.get("quantity", 1.0))
            u_price = float(it.get("unit_price", 0.0))
            tot_price = round(qty * u_price, 2)
            calc_subtotal += tot_price
            it_disc = float(it.get("discount", 0.0))
            it_tax = float(it.get("tax", 0.0))
            it_fee = float(it.get("fee", 0.0))
            it_dep = float(it.get("deposit", 0.0))
            parsed_items.append(
                ParsedLineItem(
                    item=name,
                    brand=str(it.get("brand", "Generic")),
                    category=str(it.get("category", "General")),
                    quantity=qty,
                    pack_size=float(it.get("pack_size", 1.0)),
                    unit=str(it.get("unit", "ea")),
                    unit_price=u_price,
                    total_price=tot_price,
                    discount=it_disc,
                    fee=it_fee,
                    tax=it_tax,
                    deposit=it_dep,
                )
            )

        if subtotal is None:
            subtotal = round(calc_subtotal, 2)
        else:
            subtotal = round(subtotal, 2)

        paid_total = round(subtotal - discount + tax + fee + deposit, 2)
        if payment_amount is None:
            payment_amount = paid_total

        # Build ground-truth ParsedReceipt
        clean_date = receipt_date.split()[0] if " " in receipt_date else receipt_date
        clean_rcpt_id = receipt_id.replace("FOLIO:", "").replace("TICKET:", "").strip()
        gt_receipt = ParsedReceipt(
            receipt_id=f"rcpt-{clean_rcpt_id}" if not clean_rcpt_id.startswith("rcpt-") else clean_rcpt_id,
            receipt_date=clean_date,
            merchant=merchant,
            currency=currency,
            items=parsed_items,
            subtotal=subtotal,
            discount_total=round(discount, 2),
            tax_total=round(tax, 2),
            fee_total=round(fee, 2),
            deposit_total=round(deposit, 2),
            paid_total=paid_total,
            is_balanced=True,
            balance_delta=0.0,
            store_id=store_id,
            confidence=1.0,
        )

        # Plan the layout elements to estimate total image height
        # Structure:
        # Header: Merchant title, Address/Store, Receipt ID, Date, Divider
        # Body: Items (Name left, Price right; optional quantity sub-row)
        # Divider
        # Footer: Subtotal, Discount (if > 0), Tax, Total, Tender, Change, Divider, Footer msg
        divider_str = "-" * int((self.canvas_width - 2 * self.margin_x) / 7.5)

        layout_lines: list[tuple[str, str | None, str]] = []
        # Tuples of (left_text, right_text, alignment: 'center' | 'columns')
        merchant_header = f"{merchant.upper()} #{store_id}" if store_id else merchant.upper()
        layout_lines.append((merchant_header, None, "center"))
        if address:
            layout_lines.append((address, None, "center"))
        layout_lines.append((receipt_id, None, "center"))
        layout_lines.append((receipt_date, None, "center"))
        layout_lines.append((divider_str, None, "center"))

        for it in parsed_items:
            price_str = f"{it.total_price:.2f}"
            layout_lines.append((it.item, price_str, "columns"))
            if it.quantity != 1.0:
                qty_str = f"  {it.quantity:g} x {it.unit_price:.2f}"
                layout_lines.append((qty_str, None, "left"))

        layout_lines.append((divider_str, None, "center"))
        layout_lines.append(("SUBTOTAL", f"{subtotal:.2f}", "columns"))

        if discount > 0:
            disc_label = "DESCUENTO" if currency.upper() == "MXN" else "DISCOUNT"
            layout_lines.append((disc_label, f"{discount:.2f}", "columns"))

        if tax > 0 or "IVA" in tax_label.upper() or "TAX" in tax_label.upper():
            layout_lines.append((tax_label, f"{tax:.2f}", "columns"))

        if fee > 0:
            layout_lines.append(("PROPINA / FEE", f"{fee:.2f}", "columns"))

        layout_lines.append(("TOTAL", f"{paid_total:.2f}", "columns"))

        # Payment / Tender
        layout_lines.append((payment_method.upper(), f"{payment_amount:.2f}", "columns"))
        change = round(payment_amount - paid_total, 2)
        if change > 0:
            change_label = "CAMBIO" if currency.upper() == "MXN" else "CHANGE"
            layout_lines.append((change_label, f"{change:.2f}", "columns"))

        layout_lines.append((divider_str, None, "center"))
        if footer_message:
            layout_lines.append((footer_message, None, "center"))

        # Compute canvas height
        total_content_height = self.margin_top + len(layout_lines) * self.line_height + self.margin_bottom
        canvas_height = max(total_content_height, 320)

        # Create PIL image canvas
        image = Image.new("RGB", (self.canvas_width, canvas_height), self.bg_color)
        draw = ImageDraw.Draw(image)

        # Render layout and track bounding boxes
        ground_truth_blocks: list[OCRTextBlock] = []
        current_y = float(self.margin_top)

        right_margin = self.canvas_width - self.margin_x

        for left_text, right_text, align in layout_lines:
            if align == "center":
                bbox = draw.textbbox((0, 0), left_text, font=self.font)
                text_w = bbox[2] - bbox[0]
                text_h = max(bbox[3] - bbox[1], 10)
                x = (self.canvas_width - text_w) / 2.0
                draw.text((x, current_y), left_text, fill=self.text_color, font=self.font)

                # Track block with normalized coordinates
                norm_box = BoundingBox(
                    x=round(x / self.canvas_width, 4),
                    y=round(current_y / canvas_height, 4),
                    width=round(text_w / self.canvas_width, 4),
                    height=round(text_h / canvas_height, 4),
                )
                ground_truth_blocks.append(OCRTextBlock(text=left_text, bbox=norm_box, confidence=1.0))

            elif align == "left":
                bbox = draw.textbbox((self.margin_x, current_y), left_text, font=self.font)
                text_w = bbox[2] - bbox[0]
                text_h = max(bbox[3] - bbox[1], 10)
                draw.text((self.margin_x, current_y), left_text, fill=self.text_color, font=self.font)

                norm_box = BoundingBox(
                    x=round(self.margin_x / self.canvas_width, 4),
                    y=round(current_y / canvas_height, 4),
                    width=round(text_w / self.canvas_width, 4),
                    height=round(text_h / canvas_height, 4),
                )
                ground_truth_blocks.append(OCRTextBlock(text=left_text, bbox=norm_box, confidence=1.0))

            elif align == "columns":
                # Left column text
                bbox_l = draw.textbbox((self.margin_x, current_y), left_text, font=self.font)
                text_l_w = bbox_l[2] - bbox_l[0]
                text_l_h = max(bbox_l[3] - bbox_l[1], 10)
                draw.text((self.margin_x, current_y), left_text, fill=self.text_color, font=self.font)

                norm_box_l = BoundingBox(
                    x=round(self.margin_x / self.canvas_width, 4),
                    y=round(current_y / canvas_height, 4),
                    width=round(text_l_w / self.canvas_width, 4),
                    height=round(text_l_h / canvas_height, 4),
                )
                ground_truth_blocks.append(OCRTextBlock(text=left_text, bbox=norm_box_l, confidence=1.0))

                # Right column text (price)
                if right_text:
                    bbox_r = draw.textbbox((0, 0), right_text, font=self.font)
                    text_r_w = bbox_r[2] - bbox_r[0]
                    text_r_h = max(bbox_r[3] - bbox_r[1], 10)
                    rx = right_margin - text_r_w
                    draw.text((rx, current_y), right_text, fill=self.text_color, font=self.font)

                    norm_box_r = BoundingBox(
                        x=round(rx / self.canvas_width, 4),
                        y=round(current_y / canvas_height, 4),
                        width=round(text_r_w / self.canvas_width, 4),
                        height=round(text_r_h / canvas_height, 4),
                    )
                    ground_truth_blocks.append(OCRTextBlock(text=right_text, bbox=norm_box_r, confidence=1.0))

            current_y += self.line_height

        if mode.upper() == "L":
            image = image.convert("L")

        return image, ground_truth_blocks, gt_receipt


def apply_distortions(
    image: Image.Image,
    rotation_deg: float = 2.0,
    noise_level: float = 0.02,
    fade_contrast: float = 0.85,
    vignette: bool = True,
    seed: int | None = None,
) -> Image.Image:
    """Apply photometric, geometric, and thermal printing degradation distortions.

    Simulates realistic smartphone receipt captures:
    1. Slight rotation / camera tilt with bilinear interpolation.
    2. Thermal print head fading via contrast adjustment.
    3. Paper shading / camera perspective vignetting.
    4. Salt-and-pepper / Gaussian grain noise.

    Args:
        image: Source PIL image.
        rotation_deg: Degrees of rotation/tilt (-10.0 to 10.0).
        noise_level: Grain noise blending intensity (0.0 to 0.2).
        fade_contrast: Contrast factor (1.0 = normal, < 1.0 = faded thermal print).
        vignette: Whether to apply subtle peripheral lighting falloff.
        seed: Optional RNG seed for deterministic distortions.

    Returns:
        Distorted PIL image conforming to original color mode.
    """
    orig_mode = image.mode
    work_img = image.convert("RGB")
    w, h = work_img.size

    rng = random.Random(seed)

    # 1. Geometric Tilt / Rotation
    if abs(rotation_deg) > 0.01:
        # Determine background fill color
        bg_fill = (252, 252, 250)
        work_img = work_img.rotate(
            rotation_deg,
            resample=Image.Resampling.BILINEAR,
            expand=False,
            fillcolor=bg_fill,
        )

    # 2. Thermal Print Degradation (Contrast Fading)
    if fade_contrast != 1.0:
        enhancer = ImageEnhance.Contrast(work_img)
        work_img = enhancer.enhance(max(0.1, fade_contrast))

    # 3. Vignetting / Lighting Falloff
    if vignette:
        # Generate low-res radial mask and smoothly upscale
        sw, sh = max(16, w // 10), max(16, h // 10)
        v_small = Image.new("L", (sw, sh))
        cx, cy = sw / 2.0, sh / 2.0
        max_dist = math.hypot(cx, cy)
        v_pix = [
            int(255 * (1.0 - 0.20 * ((math.hypot(x - cx, y - cy) / max_dist) ** 1.5)))
            for y in range(sh)
            for x in range(sw)
        ]
        v_small.putdata(v_pix)
        v_mask = v_small.resize((w, h), Image.Resampling.BILINEAR)

        # Composite against slightly shaded peripheral tone
        shaded_backdrop = Image.new("RGB", (w, h), (185, 185, 182))
        work_img = Image.composite(work_img, shaded_backdrop, v_mask)

    # 4. Sensor Grain / Paper Texture Noise
    if noise_level > 0.001:
        sw, sh = max(16, w // 6), max(16, h // 6)
        noise_small = Image.new("L", (sw, sh))
        # Uniform grain around neutral midpoint (128)
        noise_pix = [rng.randint(112, 144) for _ in range(sw * sh)]
        noise_small.putdata(noise_pix)
        noise_big = noise_small.resize((w, h), Image.Resampling.BILINEAR).convert("RGB")
        work_img = ImageChops.blend(work_img, noise_big, min(noise_level, 0.25))

    if orig_mode != "RGB":
        return work_img.convert(orig_mode)
    return work_img

