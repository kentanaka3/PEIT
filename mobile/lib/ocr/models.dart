/// OCR data models conforming to PEIT strict 25-column ledger semantics.
library peit_ocr_models;

import '../data/schema_constants.dart';
import '../models/receipt_entry.dart';

/// 2D Bounding box with normalized coordinates in [0.0, 1.0].
class BoundingBox {
  final double x;
  final double y;
  final double width;
  final double height;

  const BoundingBox({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
  });

  double get right => x + width;
  double get bottom => y + height;
  double get centerX => x + width / 2.0;
  double get centerY => y + height / 2.0;

  Map<String, dynamic> toJson() => {
    'x': x,
    'y': y,
    'width': width,
    'height': height,
  };

  factory BoundingBox.fromJson(Map<String, dynamic> json) => BoundingBox(
    x: (json['x'] as num).toDouble(),
    y: (json['y'] as num).toDouble(),
    width: (json['width'] as num).toDouble(),
    height: (json['height'] as num).toDouble(),
  );

  @override
  String toString() => 'BoundingBox(x: $x, y: $y, w: $width, h: $height)';
}

/// Extracted OCR text unit with spatial bounding box and confidence score.
class OCRTextBlock {
  final String text;
  final BoundingBox bbox;
  final double confidence;

  const OCRTextBlock({
    required this.text,
    required this.bbox,
    this.confidence = 1.0,
  });

  Map<String, dynamic> toJson() => {
    'text': text,
    'bbox': bbox.toJson(),
    'confidence': confidence,
  };

  factory OCRTextBlock.fromJson(Map<String, dynamic> json) => OCRTextBlock(
    text: json['text'] as String,
    bbox: BoundingBox.fromJson(json['bbox'] as Map<String, dynamic>),
    confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
  );
}

/// Extracted and normalized receipt line item candidate.
class ParsedLineItem {
  String item;
  String brand;
  String category;
  double quantity;
  double packSize;
  String unit;
  double unitPrice;
  double totalPrice;
  double discount;
  double fee;
  double tax;
  double deposit;
  String eventType;
  String storeTier;
  double storeRating;
  String brandTier;
  double brandRating;
  String productTier;
  double productRating;
  String availability;
  String notes;
  double confidence;
  BoundingBox? bbox;

  ParsedLineItem({
    required this.item,
    this.brand = 'Generic',
    this.category = 'General',
    this.quantity = 1.0,
    this.packSize = 1.0,
    this.unit = 'ea',
    this.unitPrice = 0.0,
    this.totalPrice = 0.0,
    this.discount = 0.0,
    this.fee = 0.0,
    this.tax = 0.0,
    this.deposit = 0.0,
    this.eventType = 'one_off',
    this.storeTier = 'A',
    this.storeRating = 5.0,
    this.brandTier = 'A',
    this.brandRating = 5.0,
    this.productTier = 'A',
    this.productRating = 5.0,
    this.availability = 'in_stock',
    this.notes = '',
    this.confidence = 1.0,
    this.bbox,
  });

  /// Computed net total for this line: total_price - discount + fee + tax + deposit
  double get netTotal => totalPrice - discount + fee + tax + deposit;

  /// Check whether line multiplication holds: |qty * unit_price - total_price| < 0.05
  bool get isMathValid {
    final expected = quantity * unitPrice;
    return (expected - totalPrice).abs() < 0.05;
  }

  ParsedLineItem copyWith({
    String? item,
    String? brand,
    String? category,
    double? quantity,
    double? packSize,
    String? unit,
    double? unitPrice,
    double? totalPrice,
    double? discount,
    double? fee,
    double? tax,
    double? deposit,
    String? eventType,
    String? storeTier,
    double? storeRating,
    String? brandTier,
    double? brandRating,
    String? productTier,
    double? productRating,
    String? availability,
    String? notes,
    double? confidence,
    BoundingBox? bbox,
  }) {
    return ParsedLineItem(
      item: item ?? this.item,
      brand: brand ?? this.brand,
      category: category ?? this.category,
      quantity: quantity ?? this.quantity,
      packSize: packSize ?? this.packSize,
      unit: unit ?? this.unit,
      unitPrice: unitPrice ?? this.unitPrice,
      totalPrice: totalPrice ?? this.totalPrice,
      discount: discount ?? this.discount,
      fee: fee ?? this.fee,
      tax: tax ?? this.tax,
      deposit: deposit ?? this.deposit,
      eventType: eventType ?? this.eventType,
      storeTier: storeTier ?? this.storeTier,
      storeRating: storeRating ?? this.storeRating,
      brandTier: brandTier ?? this.brandTier,
      brandRating: brandRating ?? this.brandRating,
      productTier: productTier ?? this.productTier,
      productRating: productRating ?? this.productRating,
      availability: availability ?? this.availability,
      notes: notes ?? this.notes,
      confidence: confidence ?? this.confidence,
      bbox: bbox ?? this.bbox,
    );
  }

  Map<String, dynamic> toJson() => {
    'item': item,
    'brand': brand,
    'category': category,
    'quantity': quantity,
    'pack_size': packSize,
    'unit': unit,
    'unit_price': unitPrice,
    'total_price': totalPrice,
    'discount': discount,
    'fee': fee,
    'tax': tax,
    'deposit': deposit,
    'event_type': eventType,
    'store_tier': storeTier,
    'store_rating': storeRating,
    'brand_tier': brandTier,
    'brand_rating': brandRating,
    'product_tier': productTier,
    'product_rating': productRating,
    'availability': availability,
    'notes': notes,
    'confidence': confidence,
    if (bbox != null) 'bbox': bbox!.toJson(),
  };

  factory ParsedLineItem.fromJson(Map<String, dynamic> json) => ParsedLineItem(
    item: json['item'] as String,
    brand: (json['brand'] as String?) ?? 'Generic',
    category: (json['category'] as String?) ?? 'General',
    quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
    packSize: (json['pack_size'] as num?)?.toDouble() ?? 1.0,
    unit: (json['unit'] as String?) ?? 'ea',
    unitPrice: (json['unit_price'] as num?)?.toDouble() ?? 0.0,
    totalPrice: (json['total_price'] as num?)?.toDouble() ?? 0.0,
    discount: (json['discount'] as num?)?.toDouble() ?? 0.0,
    fee: (json['fee'] as num?)?.toDouble() ?? 0.0,
    tax: (json['tax'] as num?)?.toDouble() ?? 0.0,
    deposit: (json['deposit'] as num?)?.toDouble() ?? 0.0,
    eventType: (json['event_type'] as String?) ?? 'one_off',
    storeTier: (json['store_tier'] as String?) ?? 'A',
    storeRating: (json['store_rating'] as num?)?.toDouble() ?? 5.0,
    brandTier: (json['brand_tier'] as String?) ?? 'A',
    brandRating: (json['brand_rating'] as num?)?.toDouble() ?? 5.0,
    productTier: (json['product_tier'] as String?) ?? 'A',
    productRating: (json['product_rating'] as num?)?.toDouble() ?? 5.0,
    availability: (json['availability'] as String?) ?? 'in_stock',
    notes: (json['notes'] as String?) ?? '',
    confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
    bbox: json['bbox'] != null ? BoundingBox.fromJson(json['bbox'] as Map<String, dynamic>) : null,
  );
}

/// Structured representation of a parsed receipt conforming to PEIT semantics.
class ParsedReceipt {
  final String receiptId;
  final String receiptDate; // YYYY-MM-DD
  final String merchant;
  final String currency; // MXN, USD, EUR, CAD
  final List<ParsedLineItem> items;
  final double subtotal;
  final double discountTotal;
  final double taxTotal;
  final double feeTotal;
  final double depositTotal;
  final double paidTotal;
  final bool isBalanced;
  final double balanceDelta;
  final double confidence;
  final String storeId;
  final String rawText;

  const ParsedReceipt({
    required this.receiptId,
    required this.receiptDate,
    required this.merchant,
    this.currency = 'MXN',
    this.items = const [],
    this.subtotal = 0.0,
    this.discountTotal = 0.0,
    this.taxTotal = 0.0,
    this.feeTotal = 0.0,
    this.depositTotal = 0.0,
    this.paidTotal = 0.0,
    this.isBalanced = false,
    this.balanceDelta = 0.0,
    this.confidence = 1.0,
    this.storeId = '',
    this.rawText = '',
  });

  /// Convert parsed receipt items into strict 25-column dictionary rows for PEIT.
  ///
  /// Conforms to PEIT sign conventions:
  /// - paid_total is negative (< 0) for expenditures
  /// - discount is positive (> 0)
  /// - tax, fee, deposit are negative (<= 0)
  List<Map<String, dynamic>> toPeitRows() {
    final List<Map<String, dynamic>> rows = [];
    final nItems = items.length;

    // Calculate unallocated amounts to distribute across items
    final itemSumDiscount = items.fold(0.0, (acc, it) => acc + it.discount);
    final itemSumTax = items.fold(0.0, (acc, it) => acc + it.tax);
    final itemSumFee = items.fold(0.0, (acc, it) => acc + it.fee);
    final itemSumDeposit = items.fold(0.0, (acc, it) => acc + it.deposit);

    final unallocatedDiscount = discountTotal > itemSumDiscount && nItems > 0
        ? (discountTotal - itemSumDiscount) / nItems
        : 0.0;
    final unallocatedTax = taxTotal > itemSumTax && nItems > 0
        ? (taxTotal - itemSumTax) / nItems
        : 0.0;
    final unallocatedFee = feeTotal > itemSumFee && nItems > 0
        ? (feeTotal - itemSumFee) / nItems
        : 0.0;
    final unallocatedDeposit = depositTotal > itemSumDeposit && nItems > 0
        ? (depositTotal - itemSumDeposit) / nItems
        : 0.0;

    for (final it in items) {
      final effectiveDiscount = it.discount + unallocatedDiscount;
      final effectiveTax = it.tax + unallocatedTax;
      final effectiveFee = it.fee + unallocatedFee;
      final effectiveDeposit = it.deposit + unallocatedDeposit;

      // Expense net calculation
      final net = it.totalPrice - effectiveDiscount + effectiveTax + effectiveFee + effectiveDeposit;
      final itemPaidTotal = net > 0 ? -net : (it.totalPrice > 0 ? -it.totalPrice : 0.0);

      final row = <String, dynamic>{
        'receipt_id': receiptId,
        'receipt_date': receiptDate,
        'merchant': merchant,
        'item': it.item,
        'brand': it.brand.isNotEmpty ? it.brand : 'Generic',
        'category': it.category.isNotEmpty ? it.category : 'General',
        'quantity': it.quantity,
        'pack_size': it.packSize,
        'unit': it.unit.isNotEmpty ? it.unit : 'ea',
        'unit_price': it.unitPrice,
        'currency': currency,
        'discount': normalizeDiscountSign(effectiveDiscount),
        'fee': normalizeSurchargeSign(effectiveFee),
        'tax': normalizeSurchargeSign(effectiveTax),
        'deposit': normalizeSurchargeSign(effectiveDeposit),
        'paid_total': normalizeExpenseSign(double.parse(itemPaidTotal.abs().toStringAsFixed(2))),
        'event_type': it.eventType.isNotEmpty ? it.eventType : 'one_off',
        'store_tier': PeitSchemaConstants.validTiers.contains(it.storeTier) ? it.storeTier : 'A',
        'store_rating': it.storeRating,
        'brand_tier': PeitSchemaConstants.validTiers.contains(it.brandTier) ? it.brandTier : 'A',
        'brand_rating': it.brandRating,
        'product_tier': PeitSchemaConstants.validTiers.contains(it.productTier) ? it.productTier : 'A',
        'product_rating': it.productRating,
        'availability': PeitSchemaConstants.availabilityStatuses.contains(it.availability)
            ? it.availability
            : 'in_stock',
        'notes': it.notes,
      };

      // Verify all 25 columns exist
      assert(receiptColumns.every((col) => row.containsKey(col)),
          'Generated row missing required PEIT columns');
      assert(row.length == receiptColumns.length,
          'Generated row has invalid column count');

      rows.add(row);
    }

    return rows;
  }

  /// Convert parsed items into domain ReceiptEntryModel instances ready for SQLite insertion.
  List<ReceiptEntryModel> toReceiptEntryModels({String account = 'default:checking'}) {
    final rows = toPeitRows();
    final nowIso = DateTime.now().toUtc().toIso8601String();

    return rows.map((r) {
      final entryId = computeEntryId(
        receiptId: r['receipt_id'] as String,
        item: r['item'] as String,
        paidTotal: (r['paid_total'] as num).toDouble(),
        receiptDate: r['receipt_date'] as String,
      );

      return ReceiptEntryModel(
        entryId: entryId,
        receiptId: r['receipt_id'] as String,
        receiptDate: r['receipt_date'] as String,
        merchant: r['merchant'] as String,
        item: r['item'] as String,
        brand: r['brand'] as String,
        category: r['category'] as String,
        quantity: (r['quantity'] as num).toDouble(),
        packSize: (r['pack_size'] as num).toDouble(),
        unit: r['unit'] as String,
        unitPrice: (r['unit_price'] as num).toDouble(),
        currency: r['currency'] as String,
        discount: (r['discount'] as num).toDouble(),
        fee: (r['fee'] as num).toDouble(),
        tax: (r['tax'] as num).toDouble(),
        deposit: (r['deposit'] as num).toDouble(),
        paidTotal: (r['paid_total'] as num).toDouble(),
        eventType: r['event_type'] as String,
        storeTier: r['store_tier'] as String,
        storeRating: (r['store_rating'] as num).toDouble(),
        brandTier: r['brand_tier'] as String,
        brandRating: (r['brand_rating'] as num).toDouble(),
        productTier: r['product_tier'] as String,
        productRating: (r['product_rating'] as num).toDouble(),
        availability: r['availability'] as String,
        notes: r['notes'] as String,
        recordedAt: nowIso,
        account: account,
        isSynced: false,
      );
    }).toList();
  }

  Map<String, dynamic> toJson() => {
    'receipt_id': receiptId,
    'receipt_date': receiptDate,
    'merchant': merchant,
    'currency': currency,
    'items': items.map((i) => i.toJson()).toList(),
    'subtotal': subtotal,
    'discount_total': discountTotal,
    'tax_total': taxTotal,
    'fee_total': feeTotal,
    'deposit_total': depositTotal,
    'paid_total': paidTotal,
    'is_balanced': isBalanced,
    'balance_delta': balanceDelta,
    'confidence': confidence,
    'store_id': storeId,
    'raw_text': rawText,
  };
}
