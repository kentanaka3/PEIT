/// Bilingual and international heuristic receipt parser for PEIT Mobile.
/// Ported from peit.ocr.parser (Python) with full support for MXN, USD, EUR, CAD,
/// multi-format date extraction, spatial line clustering, tax/discount recognition,
/// and double-entry arithmetic balancing.
library peit_ocr_parser;

import 'dart:math';
import 'models.dart';

/// Spanish month names to month integer (1-12)
const Map<String, int> spanishMonths = {
  'ene': 1, 'enero': 1,
  'feb': 2, 'febrero': 2,
  'mar': 3, 'marzo': 3,
  'abr': 4, 'abril': 4,
  'may': 5, 'mayo': 5,
  'jun': 6, 'junio': 6,
  'jul': 7, 'julio': 7,
  'ago': 8, 'agosto': 8,
  'sep': 9, 'sept': 9, 'septiembre': 9, 'set': 9,
  'oct': 10, 'octubre': 10,
  'nov': 11, 'noviembre': 11,
  'dic': 12, 'diciembre': 12,
};

/// English month names to month integer (1-12)
const Map<String, int> englishMonths = {
  'jan': 1, 'january': 1,
  'feb': 2, 'february': 2,
  'mar': 3, 'march': 3,
  'apr': 4, 'april': 4,
  'may': 5,
  'jun': 6, 'june': 6,
  'jul': 7, 'july': 7,
  'aug': 8, 'august': 8,
  'sep': 9, 'sept': 9, 'september': 9,
  'oct': 10, 'october': 10,
  'nov': 11, 'november': 11,
  'dec': 12, 'december': 12,
};

final Map<String, int> allMonths = {...spanishMonths, ...englishMonths};

/// Known merchant patterns and their canonical names
final List<MapEntry<RegExp, String>> knownMerchants = [
  MapEntry(RegExp(r'\bREAL\s+CANADIAN\s+SUPERSTORE\b|\bSUPERSTORE\b', caseSensitive: false), 'Real Canadian Superstore'),
  MapEntry(RegExp(r'\bSAVE-?ON-?FOODS\b', caseSensitive: false), 'Save-On-Foods'),
  MapEntry(RegExp(r'\bOXXO\b', caseSensitive: false), 'OXXO'),
  MapEntry(RegExp(r'\bWALMART\b', caseSensitive: false), 'Walmart'),
  MapEntry(RegExp(r'\bBODEGA\s+AURRERA\b', caseSensitive: false), 'Bodega Aurrera'),
  MapEntry(RegExp(r'\bCOSTCO(?:\s+WHOLESALE)?\b', caseSensitive: false), 'Costco'),
  MapEntry(RegExp(r'\bCHEDRAUI\b', caseSensitive: false), 'Chedraui'),
  MapEntry(RegExp(r'\bSORIANA\b', caseSensitive: false), 'Soriana'),
  MapEntry(RegExp(r'\bH-?E-?B\b', caseSensitive: false), 'HEB'),
  MapEntry(RegExp(r'\bTARGET\b', caseSensitive: false), 'Target'),
  MapEntry(RegExp(r"\bTRADER\s+JOE'?S\b", caseSensitive: false), "Trader Joe's"),
  MapEntry(RegExp(r'\bSEVEN\s+ELEVEN\b|\b7-ELEVEN\b', caseSensitive: false), '7-Eleven'),
  MapEntry(RegExp(r'\bFARMACIAS\s+DEL\s+AHORRO\b', caseSensitive: false), 'Farmacias del Ahorro'),
  MapEntry(RegExp(r'\bFARMACIAS\s+GUADALAJARA\b', caseSensitive: false), 'Farmacias Guadalajara'),
  MapEntry(RegExp(r'\bLA\s+COMER\b', caseSensitive: false), 'La Comer'),
  MapEntry(RegExp(r'\bCITY\s+MARKET\b', caseSensitive: false), 'City Market'),
  MapEntry(RegExp(r'\bFRESKO\b', caseSensitive: false), 'Fresko'),
  MapEntry(RegExp(r'\bHOME\s+DEPOT\b', caseSensitive: false), 'The Home Depot'),
  MapEntry(RegExp(r'\bWHOLE\s+FOODS\b', caseSensitive: false), 'Whole Foods Market'),
  MapEntry(RegExp(r'\bKROGER\b', caseSensitive: false), 'Kroger'),
];

/// Common tax indicators
const List<String> taxKeywords = [
  'iva', 'ieps', 'tax', 'sales tax', 'vat', 'impuesto', 'tasa 16%', 'tasa 8%', 'tasa 0%',
  'gst', 'pst', 'hst', 'gst 5%', 'pst 7%',
];

/// Common discount indicators
const List<String> discountKeywords = [
  'desc', 'descuento', 'disc', 'discount', 'ahorro', 'bonificacion', 'rebaja', 'cupon',
];

/// Subtotal keywords
const List<String> subtotalKeywords = [
  'subtotal', 'sub-total', 'sub total',
];

/// Paid total / final total keywords
const List<String> totalKeywords = [
  'total', 'total a pagar', 'gran total', 'importe total', 'paid total', 'amount paid',
  'balance due', 'monto pagado', 'total mxn', 'total usd',
];

/// Non-item footer / metadata lines to ignore as line item candidates
const List<String> footerKeywords = [
  'cambio', 'change', 'efectivo', 'cash', 'tarjeta', 'card', 'visa', 'mastercard',
  'amex', 'american express', 'debito', 'debit', 'credito', 'credit',
  'propina', 'tip', 'gratuity', 'puntos', 'pago', 'tendered', 'recibido',
  'cajero', 'caja', 'articulos', 'items sold', 'piezas', 'ticket', 'folio',
  'factura', 'rfc', 'telefono', 'tel:', 'gracias por su compra', 'thank you',
  'vuelva pronto', 'autorizacion', 'aprobacion', 'cliente', 'afiliacion',
];

/// ReceiptParser parses raw text lines or OCRTextBlock arrays into structured ParsedReceipt.
class ReceiptParser {
  final String defaultCurrency;

  ReceiptParser({this.defaultCurrency = 'MXN'});

  /// Parse structured OCR text blocks with 2D spatial baselines
  ParsedReceipt parseBlocks(List<OCRTextBlock> blocks) {
    if (blocks.isEmpty) {
      return _createEmptyReceipt();
    }

    // Cluster blocks into spatial lines
    final lines = _clusterBlocksIntoLines(blocks);
    return _parseFromSpatialLines(lines, blocks);
  }

  /// Fallback line-by-line parser when bounding box coordinates are absent
  ParsedReceipt parseText(String rawText) {
    final lines = rawText.split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty).toList();
    if (lines.isEmpty) {
      return _createEmptyReceipt();
    }

    final syntheticBlocks = <OCRTextBlock>[];
    for (int i = 0; i < lines.length; i++) {
      final y = i / max(lines.length, 1);
      final h = 1.0 / max(lines.length, 1);
      final bbox = BoundingBox(x: 0.0, y: y, width: 1.0, height: h);
      syntheticBlocks.add(OCRTextBlock(text: lines[i], bbox: bbox, confidence: 1.0));
    }

    return parseBlocks(syntheticBlocks);
  }

  /// Cluster OCR text blocks into logical lines based on vertical overlap
  List<List<OCRTextBlock>> _clusterBlocksIntoLines(List<OCRTextBlock> blocks) {
    if (blocks.isEmpty) return [];

    final sortedBlocks = List<OCRTextBlock>.from(blocks)
      ..sort((a, b) {
        final cmp = a.bbox.centerY.compareTo(b.bbox.centerY);
        return cmp != 0 ? cmp : a.bbox.x.compareTo(b.bbox.x);
      });

    final lines = <List<OCRTextBlock>>[];
    var currentLine = <OCRTextBlock>[sortedBlocks.first];

    for (int i = 1; i < sortedBlocks.length; i++) {
      final block = sortedBlocks[i];
      final lastBlock = currentLine.last;

      double refHeight = min(block.bbox.height, lastBlock.bbox.height);
      if (refHeight <= 0) refHeight = 0.02;

      final centerDiff = (block.bbox.centerY - lastBlock.bbox.centerY).abs();
      final threshold = refHeight * 0.65;

      if (centerDiff <= threshold) {
        currentLine.add(block);
      } else {
        currentLine.sort((a, b) => a.bbox.x.compareTo(b.bbox.x));
        lines.add(currentLine);
        currentLine = [block];
      }
    }

    if (currentLine.isNotEmpty) {
      currentLine.sort((a, b) => a.bbox.x.compareTo(b.bbox.x));
      lines.add(currentLine);
    }

    return lines;
  }

  /// Extract metadata, line items, taxes, and footer balances from spatial lines
  ParsedReceipt _parseFromSpatialLines(
    List<List<OCRTextBlock>> lines,
    List<OCRTextBlock> allBlocks,
  ) {
    final rawFullText = lines.map((l) => l.map((b) => b.text).join(' ')).join('\n');
    final flatLineTexts = lines.map((l) => l.map((b) => b.text).join(' ').trim()).toList();

    // 1. Currency Detection
    final currency = _detectCurrency(rawFullText);

    // 2. Date Detection
    final receiptDate = _detectDate(flatLineTexts);

    // 3. Merchant and Store Detection
    final merchantInfo = _detectMerchantAndStore(flatLineTexts);
    final merchant = merchantInfo.key;
    final storeId = merchantInfo.value;

    // 4. Receipt ID / Ticket #
    final receiptId = _detectReceiptId(flatLineTexts, merchant, receiptDate);

    // 5. Extract Totals, Taxes, Discounts from footer
    final totals = _extractFinancialTotals(flatLineTexts, lines);
    var subtotal = totals['subtotal']!;
    final discountTotal = totals['discountTotal']!;
    final taxTotal = totals['taxTotal']!;
    final feeTotal = totals['feeTotal']!;
    final depositTotal = totals['depositTotal']!;
    var paidTotal = totals['paidTotal']!;
    final footerStartIdx = totals['footerStartIdx']!.toInt();

    // 6. Extract Line Items (lines before footer)
    final itemCandidateLines = footerStartIdx > 0 && footerStartIdx <= lines.length
        ? lines.sublist(0, footerStartIdx)
        : lines;
    final items = _extractLineItems(itemCandidateLines);

    // 7. Arithmetic Balancing & Verification
    final itemsSum = items.fold(0.0, (acc, it) => acc + it.totalPrice);
    if (paidTotal == 0.0) {
      if (subtotal > 0.0) {
        paidTotal = subtotal - discountTotal + taxTotal + feeTotal + depositTotal;
      } else {
        paidTotal = itemsSum - discountTotal + taxTotal + feeTotal + depositTotal;
      }
    }

    if (subtotal == 0.0 && itemsSum > 0) {
      subtotal = itemsSum;
    }

    final calculatedExpectedTotal = itemsSum - discountTotal + taxTotal + feeTotal + depositTotal;
    final balanceDelta = double.parse((paidTotal - calculatedExpectedTotal).toStringAsFixed(2));
    final isBalanced = balanceDelta.abs() < 0.05;

    final confidence = _computeOverallConfidence(
      merchant: merchant,
      receiptDate: receiptDate,
      items: items,
      paidTotal: paidTotal,
      isBalanced: isBalanced,
    );

    return ParsedReceipt(
      receiptId: receiptId,
      receiptDate: receiptDate,
      merchant: merchant,
      currency: currency,
      items: items,
      subtotal: double.parse(subtotal.toStringAsFixed(2)),
      discountTotal: double.parse(discountTotal.toStringAsFixed(2)),
      taxTotal: double.parse(taxTotal.toStringAsFixed(2)),
      feeTotal: double.parse(feeTotal.toStringAsFixed(2)),
      depositTotal: double.parse(depositTotal.toStringAsFixed(2)),
      paidTotal: double.parse(paidTotal.toStringAsFixed(2)),
      isBalanced: isBalanced,
      balanceDelta: balanceDelta,
      confidence: double.parse(confidence.toStringAsFixed(3)),
      storeId: storeId,
      rawText: rawFullText,
    );
  }

  /// Detect currency code (MXN, USD, EUR, CAD) or fallback to default
  String _detectCurrency(String text) {
    final upper = text.toUpperCase();
    if (RegExp(r'\b(EUR|€|EUROS)\b').hasMatch(upper)) return 'EUR';
    if (RegExp(r'\b(CAD|CAD\$|CANADIAN\s+DOLLARS)\b').hasMatch(upper)) return 'CAD';
    if (RegExp(r'\b(USD|U\.S\.D|US\s*\$)\b').hasMatch(upper)) return 'USD';
    if (RegExp(r'\b(MXN|M\.N\.|PESOS|MN)\b').hasMatch(upper)) return 'MXN';
    return defaultCurrency;
  }

  /// Extract receipt date in YYYY-MM-DD format
  String _detectDate(List<String> lines) {
    final targetLines = [
      ...lines.take(20),
      if (lines.length > 20) ...lines.skip(max(0, lines.length - 10)),
    ];

    for (final line in targetLines) {
      final found = _parseDateString(line);
      if (found != null) return found;
    }

    // Fallback to today's date formatted as YYYY-MM-DD
    final now = DateTime.now();
    return "${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}";
  }

  /// Attempt to parse date patterns from text line
  String? _parseDateString(String text) {
    // 1. YYYY-MM-DD or YYYY/MM/DD
    final m1 = RegExp(r'\b(20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b').firstMatch(text);
    if (m1 != null) {
      final y = int.parse(m1.group(1)!);
      final month = int.parse(m1.group(2)!);
      final d = int.parse(m1.group(3)!);
      return _formatIsoDate(y, month, d);
    }

    // 2. DD/MM/YYYY or DD-MM-YYYY
    final m2 = RegExp(r'\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](20\d{2})\b').firstMatch(text);
    if (m2 != null) {
      final d = int.parse(m2.group(1)!);
      final month = int.parse(m2.group(2)!);
      final y = int.parse(m2.group(3)!);
      return _formatIsoDate(y, month, d);
    }

    // 3. MM/DD/YYYY or MM-DD-YYYY
    final m3 = RegExp(r'\b(0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])[-/.](20\d{2})\b').firstMatch(text);
    if (m3 != null) {
      final month = int.parse(m3.group(1)!);
      final d = int.parse(m3.group(2)!);
      final y = int.parse(m3.group(3)!);
      return _formatIsoDate(y, month, d);
    }

    // 4. DD Mon YYYY / DD-Mon-YYYY (e.g. 15 MAR 2026, 15/Mar/2026, 15 de marzo de 2026)
    final m4 = RegExp(
      r'\b(0?[1-9]|[12]\d|3[01])\s*(?:de|\s|[-/.])\s*([a-zA-Z]{3,10})\s*(?:de|\s|[-/.])\s*(20\d{2})\b',
      caseSensitive: false,
    ).firstMatch(text);
    if (m4 != null) {
      final d = int.parse(m4.group(1)!);
      final monStr = m4.group(2)!.toLowerCase();
      final y = int.parse(m4.group(3)!);
      final mon = allMonths[monStr] ?? (monStr.length >= 3 ? allMonths[monStr.substring(0, 3)] : null);
      if (mon != null) {
        return _formatIsoDate(y, mon, d);
      }
    }

    // 5. Month DD, YYYY (e.g. March 15, 2026)
    final m5 = RegExp(
      r'\b([a-zA-Z]{3,10})\s+(0?[1-9]|[12]\d|3[01]),?\s+(20\d{2})\b',
      caseSensitive: false,
    ).firstMatch(text);
    if (m5 != null) {
      final monStr = m5.group(1)!.toLowerCase();
      final d = int.parse(m5.group(2)!);
      final y = int.parse(m5.group(3)!);
      final mon = allMonths[monStr] ?? (monStr.length >= 3 ? allMonths[monStr.substring(0, 3)] : null);
      if (mon != null) {
        return _formatIsoDate(y, mon, d);
      }
    }

    // 6. DD/MM/YY (2-digit year)
    final m6 = RegExp(r'\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](2[0-9])\b').firstMatch(text);
    if (m6 != null) {
      final d = int.parse(m6.group(1)!);
      final month = int.parse(m6.group(2)!);
      final y = 2000 + int.parse(m6.group(3)!);
      return _formatIsoDate(y, month, d);
    }

    return null;
  }

  String? _formatIsoDate(int y, int m, int d) {
    try {
      final dt = DateTime(y, m, d);
      if (dt.year == y && dt.month == m && dt.day == d) {
        return "${y.toString().padLeft(4, '0')}-${m.toString().padLeft(2, '0')}-${d.toString().padLeft(2, '0')}";
      }
    } catch (_) {}
    return null;
  }

  /// Extract merchant name and optional store/branch number
  MapEntry<String, String> _detectMerchantAndStore(List<String> lines) {
    String storeId = '';
    for (final line in lines.take(15)) {
      final m = RegExp(r'(?:#|TIENDA|SUCURSAL|STORE|BRANCH)\s*[:#]?\s*(\d+)', caseSensitive: false).firstMatch(line);
      if (m != null) {
        storeId = m.group(1)!;
        break;
      }
    }

    for (final line in lines.take(10)) {
      for (final entry in knownMerchants) {
        if (entry.key.hasMatch(line)) {
          return MapEntry(entry.value, storeId);
        }
      }
    }

    for (final line in lines.take(5)) {
      var cleaned = line.replaceAll(RegExp(r'[#\d]+'), '').trim();
      if (cleaned.length >= 3 && !RegExp(r'\b(TICKET|BIENVENIDO|WELCOME|FACTURA)\b', caseSensitive: false).hasMatch(cleaned)) {
        cleaned = cleaned.split(RegExp(r'[,;:\-–—]')).first.trim();
        return MapEntry(_toTitleCase(cleaned), storeId);
      }
    }

    return MapEntry('Unknown Merchant', storeId);
  }

  String _toTitleCase(String text) {
    return text.split(' ').map((word) {
      if (word.isEmpty) return '';
      return word[0].toUpperCase() + word.substring(1).toLowerCase();
    }).join(' ');
  }

  /// Find or synthesize a unique receipt identifier
  String _detectReceiptId(List<String> lines, String merchant, String receiptDate) {
    for (final line in lines) {
      final m = RegExp(r'\b(?:FOLIO|TICKET|RECIBO|RECEIPT|TRANS|TRANSACTION)\s*[:#]?\s*([A-Za-z0-9\-]+)\b', caseSensitive: false).firstMatch(line);
      if (m != null) {
        final val = m.group(1)!.trim();
        if (val.length >= 3 && !{'de', 'para', 'en'}.contains(val.toLowerCase())) {
          return 'rcpt-$val';
        }
      }
    }

    for (final line in lines) {
      final m = RegExp(r'\b(?:NO\.|REF)\s*[:#]?\s*([A-Za-z0-9\-]+)\b', caseSensitive: false).firstMatch(line);
      if (m != null) {
        final val = m.group(1)!.trim();
        if (val.length >= 3 && !{'de', 'para', 'en'}.contains(val.toLowerCase())) {
          return 'rcpt-$val';
        }
      }
    }

    final merchClean = merchant.replaceAll(RegExp(r'[^A-Za-z0-9]'), '').toLowerCase();
    final cleanPrefix = merchClean.isNotEmpty ? merchClean.substring(0, min(8, merchClean.length)) : 'mkt';
    return 'rcpt-$cleanPrefix-${receiptDate.replaceAll('-', '')}';
  }

  /// Extract financial totals and determine where the footer starts
  Map<String, double> _extractFinancialTotals(List<String> flatLines, List<List<OCRTextBlock>> lines) {
    double subtotal = 0.0;
    double discountTotal = 0.0;
    double taxTotal = 0.0;
    double feeTotal = 0.0;
    double depositTotal = 0.0;
    double paidTotal = 0.0;
    int footerStartIdx = lines.length;

    for (int idx = 0; idx < flatLines.length; idx++) {
      final lineText = flatLines[idx];
      final lower = lineText.toLowerCase();

      final isSubtotalMarker = subtotalKeywords.any((k) => lower.contains(k));
      final isTotalMarker = totalKeywords.any((k) => lower.contains(k));
      final isTaxMarker = taxKeywords.any((k) => lower.contains(k));
      final isDiscountMarker = discountKeywords.any((k) => lower.contains(k));
      final isFeeMarker = ['propina', 'tip', 'gratuity'].any((k) => lower.contains(k));

      final price = _findTrailingPrice(lineText);

      if (isSubtotalMarker && price != null) {
        subtotal = price;
        if (idx < footerStartIdx) footerStartIdx = idx;
      } else if (isTotalMarker && price != null) {
        if (!isSubtotalMarker) {
          paidTotal = price;
          if (idx < footerStartIdx) footerStartIdx = idx;
        }
      } else if (isTaxMarker && price != null) {
        taxTotal += price;
        if (idx < footerStartIdx) footerStartIdx = idx;
      } else if (isDiscountMarker && price != null) {
        discountTotal += price;
        if (idx < footerStartIdx) footerStartIdx = idx;
      } else if (isFeeMarker && price != null) {
        feeTotal += price;
        if (idx < footerStartIdx) footerStartIdx = idx;
      } else if ((isSubtotalMarker || isTotalMarker) && idx < footerStartIdx) {
        footerStartIdx = idx;
      }
    }

    return {
      'subtotal': subtotal,
      'discountTotal': discountTotal,
      'taxTotal': taxTotal,
      'feeTotal': feeTotal,
      'depositTotal': depositTotal,
      'paidTotal': paidTotal,
      'footerStartIdx': footerStartIdx.toDouble(),
    };
  }

  /// Extract individual purchased items from candidate lines
  List<ParsedLineItem> _extractLineItems(List<List<OCRTextBlock>> candidateLines) {
    final items = <ParsedLineItem>[];
    int i = 0;
    final n = candidateLines.length;

    while (i < n) {
      final lineBlocks = candidateLines[i];
      final lineText = lineBlocks.map((b) => b.text).join(' ').trim();

      if (lineText.isEmpty) {
        i++;
        continue;
      }

      // Standalone multi-quantity line (e.g. "3 x 15.00")
      final qtyMatch = _matchQuantitySpec(lineText);
      if (qtyMatch != null) {
        if (items.isNotEmpty) {
          final prev = items.last;
          prev.quantity = qtyMatch.quantity;
          prev.unitPrice = qtyMatch.unitPrice;
          if (qtyMatch.unit.isNotEmpty) prev.unit = qtyMatch.unit;
          if (qtyMatch.packSize > 0) prev.packSize = qtyMatch.packSize;
          prev.totalPrice = double.parse((qtyMatch.quantity * qtyMatch.unitPrice).toStringAsFixed(2));
        }
        i++;
        continue;
      }

      final parsedItem = _parseSingleLineItem(lineBlocks, lineText);
      if (parsedItem != null) {
        if (i + 1 < n) {
          final nextBlocks = candidateLines[i + 1];
          final nextText = nextBlocks.map((b) => b.text).join(' ').trim();
          final nextQty = _matchQuantitySpec(nextText);
          if (nextQty != null) {
            parsedItem.quantity = nextQty.quantity;
            parsedItem.unitPrice = nextQty.unitPrice;
            if (nextQty.unit.isNotEmpty) parsedItem.unit = nextQty.unit;
            if (nextQty.packSize > 0) parsedItem.packSize = nextQty.packSize;
            parsedItem.totalPrice = double.parse((nextQty.quantity * nextQty.unitPrice).toStringAsFixed(2));
            i++;
          } else if (_isDiscountLine(nextText)) {
            final discPrice = _findTrailingPrice(nextText);
            if (discPrice != null) {
              parsedItem.discount = discPrice;
            }
            i++;
          }
        }
        items.add(parsedItem);
      } else {
        // Line without price: could be standalone item description followed by price/quantity line
        if (i + 1 < n) {
          final nextBlocks = candidateLines[i + 1];
          final nextText = nextBlocks.map((b) => b.text).join(' ').trim();
          final nextQty = _matchQuantitySpec(nextText);
          if (nextQty != null) {
            final brand = _extractBrand(lineText);
            final category = _categorizeItem(lineText);
            final itemName = _cleanItemName(lineText);
            if (itemName.isNotEmpty) {
              final bbox = _combineBBoxes([...lineBlocks, ...nextBlocks]);
              final tot = double.parse((nextQty.quantity * nextQty.unitPrice).toStringAsFixed(2));
              items.add(
                ParsedLineItem(
                  item: itemName,
                  brand: brand,
                  category: category,
                  quantity: nextQty.quantity,
                  packSize: nextQty.packSize,
                  unit: nextQty.unit,
                  unitPrice: double.parse(nextQty.unitPrice.toStringAsFixed(2)),
                  totalPrice: tot,
                  bbox: bbox,
                ),
              );
              i += 2;
              continue;
            }
          }
        }
      }
      i++;
    }

    return items;
  }

  /// Parse an OCR line into a ParsedLineItem if it has an item description and price
  ParsedLineItem? _parseSingleLineItem(List<OCRTextBlock> blocks, String lineText) {
    final lower = lineText.toLowerCase();
    if (footerKeywords.any((k) => lower.contains(k)) || totalKeywords.any((k) => lower.contains(k))) {
      return null;
    }
    if (subtotalKeywords.any((k) => lower.contains(k)) || taxKeywords.any((k) => lower.contains(k))) {
      return null;
    }

    final price = _findTrailingPrice(lineText);
    if (price == null) return null;

    var descPart = _stripTrailingPrice(lineText);
    if (descPart.length < 2) return null;

    double qty = 1.0;
    double unitPrice = price;
    String unit = 'ea';
    double packSize = 1.0;

    final inlineQty = _matchInlineQuantity(descPart);
    if (inlineQty != null) {
      qty = inlineQty.quantity;
      unitPrice = inlineQty.unitPrice;
      if (inlineQty.unit.isNotEmpty) unit = inlineQty.unit;
      descPart = inlineQty.cleanedDesc;
    }

    final unitInfo = _extractPackUnit(descPart);
    if (unitInfo != null) {
      packSize = unitInfo.key;
      unit = unitInfo.value;
    }

    final brand = _extractBrand(descPart);
    final category = _categorizeItem(descPart);
    final itemName = _cleanItemName(descPart);
    if (itemName.length < 2) return null;

    final bbox = _combineBBoxes(blocks);

    return ParsedLineItem(
      item: itemName,
      brand: brand,
      category: category,
      quantity: qty,
      packSize: packSize,
      unit: unit,
      unitPrice: double.parse(unitPrice.toStringAsFixed(2)),
      totalPrice: double.parse(price.toStringAsFixed(2)),
      bbox: bbox,
    );
  }

  /// Extract a trailing monetary amount from a line of text
  double? _findTrailingPrice(String text) {
    final trimmed = text.trim();
    final m = RegExp(r'[$€]?\s*([0-9]{1,4}(?:[,\.][0-9]{3})*(?:[\.,][0-9]{2}))\s*[-*A-Za-z]?\s*$').firstMatch(trimmed);
    if (m != null) {
      final rawNum = m.group(1)!.replaceAll(',', '');
      return double.tryParse(rawNum);
    }

    final mInt = RegExp(r'[$€]\s*([0-9]+(?:\.[0-9]{1,2})?)\s*$').firstMatch(trimmed);
    if (mInt != null) {
      return double.tryParse(mInt.group(1)!);
    }

    return null;
  }

  String _stripTrailingPrice(String text) {
    var s = text.trim();
    s = s.replaceAll(RegExp(r'[$€]?\s*[0-9]{1,4}(?:[,\.][0-9]{3})*(?:[\.,][0-9]{2})\s*[-*A-Za-z]?\s*$'), '');
    s = s.replaceAll(RegExp(r'[$€]\s*[0-9]+(?:\.[0-9]{1,2})?\s*$'), '');
    return s.trim();
  }

  _QuantitySpec? _matchQuantitySpec(String text) {
    final m1 = RegExp(
      r'^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\s*(?:x|@|\*)\s*[$€]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/([a-zA-Z]+))?',
      caseSensitive: false,
    ).firstMatch(text);
    if (m1 != null) {
      final qty = double.parse(m1.group(1)!);
      final unit = (m1.group(2) ?? m1.group(4) ?? 'ea').toLowerCase();
      final unitPrice = double.parse(m1.group(3)!);
      return _QuantitySpec(qty, unitPrice, unit, 1.0);
    }

    final m2 = RegExp(
      r'CANT(?:IDAD)?\s*[:#]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:P\.U\.?|PRECIO)?\s*[:$€]?\s*([0-9]+(?:\.[0-9]+)?)',
      caseSensitive: false,
    ).firstMatch(text);
    if (m2 != null) {
      final qty = double.parse(m2.group(1)!);
      final unitPrice = double.parse(m2.group(2)!);
      return _QuantitySpec(qty, unitPrice, 'ea', 1.0);
    }

    return null;
  }

  _InlineQuantitySpec? _matchInlineQuantity(String text) {
    final m = RegExp(
      r'(.*?)\s+([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?\s*(?:x|@|\*)\s*[$€]?\s*([0-9]+(?:\.[0-9]+)?)\s*(.*)',
      caseSensitive: false,
    ).firstMatch(text);
    if (m != null) {
      final pre = m.group(1) ?? '';
      final qty = double.parse(m.group(2)!);
      final unit = (m.group(3) ?? 'ea').toLowerCase();
      final unitPrice = double.parse(m.group(4)!);
      final post = m.group(5) ?? '';
      final cleaned = '$pre $post'.trim();
      return _InlineQuantitySpec(qty, unitPrice, unit, cleaned);
    }
    return null;
  }

  bool _isDiscountLine(String text) {
    final lower = text.toLowerCase();
    return discountKeywords.any((k) => lower.contains(k));
  }

  MapEntry<double, String>? _extractPackUnit(String text) {
    final m = RegExp(r'\b([0-9]+(?:\.[0-9]+)?)\s*(ml|l|lt|g|kg|oz|lb|pk|pack|pzas?|pz)\b', caseSensitive: false).firstMatch(text);
    if (m != null) {
      final val = double.parse(m.group(1)!);
      final rawUnit = m.group(2)!.toLowerCase();
      if (rawUnit == 'lt' || rawUnit == 'l') return MapEntry(val, 'L');
      if (rawUnit == 'ml') return MapEntry(val, 'ml');
      if (rawUnit == 'kg') return MapEntry(val, 'kg');
      if (rawUnit == 'g') return MapEntry(val, 'g');
      if (['pk', 'pack', 'pza', 'pzas', 'pz'].contains(rawUnit)) return MapEntry(val, 'ea');
      return MapEntry(val, rawUnit);
    }
    return null;
  }

  String _extractBrand(String text) {
    final upper = text.toUpperCase();
    const knownBrands = [
      'LALA', 'ALPURA', 'BIMBO', 'COCA COLA', 'COCA-COLA', 'PEPSI',
      'SABRITAS', 'BARCEL', 'MARINELA', 'GAMESA', 'NESTLE', "KELLOGG'S",
      'KIRKLAND', 'GREAT VALUE', "MEMBER'S MARK", 'VALE', 'SANTA CLARA',
      'SIGMA', 'SAN RAFAEL', 'FUD', 'YOPLAIT', 'DANONE', 'HERDEZ', 'DEL MONTE',
      "TRADER JOE'S", '365', 'HEINZ', 'KRAFT', 'COLGATE', 'CREST', 'PALMOLIVE',
    ];

    for (final b in knownBrands) {
      if (RegExp(r'\b' + RegExp.escape(b) + r'\b').hasMatch(upper)) {
        return _toTitleCase(b);
      }
    }
    return 'Generic';
  }

  String _categorizeItem(String text) {
    final lower = text.toLowerCase();
    if (['leche', 'milk', 'queso', 'cheese', 'pan', 'bread', 'huevo', 'egg', 'arroz', 'rice', 'frijol', 'cereal', 'cafe', 'coffee', 'te', 'tea', 'agua', 'water', 'jugo', 'juice', 'soda', 'coca', 'refresco', 'manzana', 'apple', 'platano', 'banana', 'tomate', 'aguacate', 'carne', 'meat', 'pollo', 'chicken', 'pescado', 'fish', 'yogurt', 'galletas'].any((w) => lower.contains(w))) {
      return 'Food and beverages';
    }
    if (['jabon', 'soap', 'shampoo', 'pasta dental', 'toothpaste', 'papel', 'detergente', 'cloro', 'limpiador', 'desodorante'].any((w) => lower.contains(w))) {
      return 'Household and personal care';
    }
    if (['farmacia', 'medicina', 'aspirina', 'paracetamol', 'curitas', 'alcohol'].any((w) => lower.contains(w))) {
      return 'Health and medical';
    }
    if (['gasolina', 'gas', 'estacionamiento', 'parking', 'peaje', 'uber', 'transporte'].any((w) => lower.contains(w))) {
      return 'Transportation';
    }
    return 'General';
  }

  String _cleanItemName(String text) {
    var s = text.trim();
    s = s.replaceAll(RegExp(r'^[0-9]{5,14}\s+'), '');
    s = s.replaceAll(RegExp(r'[*#_=+]+'), ' ');
    return s.split(RegExp(r'\s+')).join(' ').trim();
  }

  BoundingBox? _combineBBoxes(List<OCRTextBlock> blocks) {
    if (blocks.isEmpty) return null;
    final minX = blocks.map((b) => b.bbox.x).reduce(min);
    final minY = blocks.map((b) => b.bbox.y).reduce(min);
    final maxR = blocks.map((b) => b.bbox.right).reduce(max);
    final maxB = blocks.map((b) => b.bbox.bottom).reduce(max);
    return BoundingBox(x: minX, y: minY, width: maxR - minX, height: maxB - minY);
  }

  double _computeOverallConfidence({
    required String merchant,
    required String receiptDate,
    required List<ParsedLineItem> items,
    required double paidTotal,
    required bool isBalanced,
  }) {
    double score = 0.0;
    if (merchant != 'Unknown Merchant') {
      score += 0.25;
    } else {
      score += 0.10;
    }

    if (receiptDate.isNotEmpty) {
      score += 0.20;
    }

    if (items.isNotEmpty) {
      score += 0.25;
      final avgItemConf = items.fold(0.0, (acc, it) => acc + it.confidence) / items.length;
      score += 0.10 * avgItemConf;
    }

    if (isBalanced) {
      score += 0.20;
    } else if (paidTotal > 0) {
      score += 0.10;
    }

    return min(score, 1.0);
  }

  ParsedReceipt _createEmptyReceipt() {
    final now = DateTime.now();
    final today = "${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}";
    return ParsedReceipt(
      receiptId: 'rcpt-unknown',
      receiptDate: today,
      merchant: 'Unknown Merchant',
      currency: defaultCurrency,
      items: const [],
      confidence: 0.0,
    );
  }
}

class _QuantitySpec {
  final double quantity;
  final double unitPrice;
  final String unit;
  final double packSize;

  _QuantitySpec(this.quantity, this.unitPrice, this.unit, this.packSize);
}

class _InlineQuantitySpec {
  final double quantity;
  final double unitPrice;
  final String unit;
  final String cleanedDesc;

  _InlineQuantitySpec(this.quantity, this.unitPrice, this.unit, this.cleanedDesc);
}

