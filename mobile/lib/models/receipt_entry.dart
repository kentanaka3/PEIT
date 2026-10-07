import 'dart:convert';
import '../data/schema.dart';
import '../data/schema_constants.dart';

/// Clean domain model representing a receipt item entry in PEIT.
/// Provides bidirectional mapping to/from SQLite map, Drift row, and 25-column REST API JSON.
class ReceiptEntryModel {
  final String entryId;
  final bool isSynced;
  final String? syncedAt;

  final String receiptId;
  final String receiptDate; // YYYY-MM-DD
  final String merchant;
  final String item;
  final String brand;
  final String category;
  final double quantity;
  final double packSize;
  final String unit;
  final double unitPrice;
  final String currency;
  final double discount;
  final double fee;
  final double tax;
  final double deposit;
  final double paidTotal;
  final String eventType;
  final String storeTier;
  final double storeRating;
  final String brandTier;
  final double brandRating;
  final String productTier;
  final double productRating;
  final String availability;
  final String notes;
  final String recordedAt;
  final String account;

  const ReceiptEntryModel({
    required this.entryId,
    this.isSynced = false,
    this.syncedAt,
    required this.receiptId,
    required this.receiptDate,
    required this.merchant,
    required this.item,
    this.brand = '',
    required this.category,
    required this.quantity,
    this.packSize = 1.0,
    required this.unit,
    required this.unitPrice,
    required this.currency,
    this.discount = 0.0,
    this.fee = 0.0,
    this.tax = 0.0,
    this.deposit = 0.0,
    required this.paidTotal,
    required this.eventType,
    this.storeTier = 'A',
    this.storeRating = 5.0,
    this.brandTier = 'A',
    this.brandRating = 5.0,
    this.productTier = 'A',
    this.productRating = 5.0,
    this.availability = 'in_stock',
    this.notes = '',
    required this.recordedAt,
    this.account = 'default:checking',
  });

  /// Factory to construct a new entry and automatically compute its deterministic SHA-256 entryId.
  factory ReceiptEntryModel.create({
    required String receiptId,
    required String receiptDate,
    required String merchant,
    required String item,
    String brand = '',
    required String category,
    required double quantity,
    double packSize = 1.0,
    required String unit,
    required double unitPrice,
    required String currency,
    double discount = 0.0,
    double fee = 0.0,
    double tax = 0.0,
    double deposit = 0.0,
    required double paidTotal,
    required String eventType,
    String storeTier = 'A',
    double storeRating = 5.0,
    String brandTier = 'A',
    double brandRating = 5.0,
    String productTier = 'A',
    double productRating = 5.0,
    String availability = 'in_stock',
    String notes = '',
    String? recordedAt,
    String account = 'default:checking',
    bool isSynced = false,
    String? syncedAt,
  }) {
    final computedId = computeEntryId(
      receiptId: receiptId,
      item: item,
      paidTotal: paidTotal,
      receiptDate: receiptDate,
    );
    final nowIso = recordedAt ?? DateTime.now().toUtc().toIso8601String();

    return ReceiptEntryModel(
      entryId: computedId,
      isSynced: isSynced,
      syncedAt: syncedAt,
      receiptId: receiptId,
      receiptDate: receiptDate,
      merchant: merchant,
      item: item,
      brand: brand,
      category: category,
      quantity: quantity,
      packSize: packSize,
      unit: unit,
      unitPrice: unitPrice,
      currency: currency,
      discount: discount,
      fee: fee,
      tax: tax,
      deposit: deposit,
      paidTotal: paidTotal,
      eventType: eventType,
      storeTier: storeTier,
      storeRating: storeRating,
      brandTier: brandTier,
      brandRating: brandRating,
      productTier: productTier,
      productRating: productRating,
      availability: availability,
      notes: notes,
      recordedAt: nowIso,
      account: account,
    );
  }

  /// Convert to SQLite column map for persistence
  Map<String, dynamic> toSqliteMap() {
    return {
      'entry_id': entryId,
      'is_synced': isSynced ? 1 : 0,
      'synced_at': syncedAt,
      'receipt_id': receiptId,
      'receipt_date': receiptDate,
      'merchant': merchant,
      'item': item,
      'brand': brand,
      'category': category,
      'quantity': quantity,
      'pack_size': packSize,
      'unit': unit,
      'unit_price': unitPrice,
      'currency': currency,
      'discount': discount,
      'fee': fee,
      'tax': tax,
      'deposit': deposit,
      'paid_total': paidTotal,
      'event_type': eventType,
      'store_tier': storeTier,
      'store_rating': storeRating,
      'brand_tier': brandTier,
      'brand_rating': brandRating,
      'product_tier': productTier,
      'product_rating': productRating,
      'availability': availability,
      'notes': notes,
      'recorded_at': recordedAt,
      'account': account,
    };
  }

  /// Construct from SQLite row map
  factory ReceiptEntryModel.fromSqliteMap(Map<String, dynamic> map) {
    return ReceiptEntryModel(
      entryId: map['entry_id'] as String,
      isSynced: (map['is_synced'] as int? ?? 0) == 1,
      syncedAt: map['synced_at'] as String?,
      receiptId: map['receipt_id'] as String,
      receiptDate: map['receipt_date'] as String,
      merchant: map['merchant'] as String,
      item: map['item'] as String,
      brand: (map['brand'] as String?) ?? '',
      category: map['category'] as String,
      quantity: (map['quantity'] as num).toDouble(),
      packSize: (map['pack_size'] as num?)?.toDouble() ?? 1.0,
      unit: map['unit'] as String,
      unitPrice: (map['unit_price'] as num).toDouble(),
      currency: map['currency'] as String,
      discount: (map['discount'] as num?)?.toDouble() ?? 0.0,
      fee: (map['fee'] as num?)?.toDouble() ?? 0.0,
      tax: (map['tax'] as num?)?.toDouble() ?? 0.0,
      deposit: (map['deposit'] as num?)?.toDouble() ?? 0.0,
      paidTotal: (map['paid_total'] as num).toDouble(),
      eventType: map['event_type'] as String,
      storeTier: (map['store_tier'] as String?) ?? 'A',
      storeRating: (map['store_rating'] as num?)?.toDouble() ?? 5.0,
      brandTier: (map['brand_tier'] as String?) ?? 'A',
      brandRating: (map['brand_rating'] as num?)?.toDouble() ?? 5.0,
      productTier: (map['product_tier'] as String?) ?? 'A',
      productRating: (map['product_rating'] as num?)?.toDouble() ?? 5.0,
      availability: (map['availability'] as String?) ?? 'in_stock',
      notes: (map['notes'] as String?) ?? '',
      recordedAt: map['recorded_at'] as String,
      account: (map['account'] as String?) ?? 'default:checking',
    );
  }

  /// Convert to strict PEIT 25-column REST JSON payload (matching desktop daemon POST /api/v1/sync/push)
  Map<String, dynamic> toSyncJson() {
    return {
      'receipt_id': receiptId,
      'receipt_date': receiptDate,
      'merchant': merchant,
      'item': item,
      'brand': brand,
      'category': category,
      'quantity': quantity,
      'pack_size': packSize,
      'unit': unit,
      'unit_price': unitPrice,
      'currency': currency,
      'discount': discount,
      'fee': fee,
      'tax': tax,
      'deposit': deposit,
      'paid_total': paidTotal,
      'event_type': eventType,
      'store_tier': storeTier,
      'store_rating': storeRating,
      'brand_tier': brandTier,
      'brand_rating': brandRating,
      'product_tier': productTier,
      'product_rating': productRating,
      'availability': availability,
      'notes': notes,
      'entry_id': entryId,
      'account': account,
      'recorded_at': recordedAt,
    };
  }

  /// Construct from REST JSON
  factory ReceiptEntryModel.fromJson(Map<String, dynamic> json) {
    return ReceiptEntryModel.create(
      receiptId: json['receipt_id'] as String,
      receiptDate: json['receipt_date'] as String,
      merchant: json['merchant'] as String,
      item: json['item'] as String,
      brand: (json['brand'] as String?) ?? '',
      category: json['category'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      packSize: (json['pack_size'] as num?)?.toDouble() ?? 1.0,
      unit: json['unit'] as String,
      unitPrice: (json['unit_price'] as num).toDouble(),
      currency: json['currency'] as String,
      discount: (json['discount'] as num?)?.toDouble() ?? 0.0,
      fee: (json['fee'] as num?)?.toDouble() ?? 0.0,
      tax: (json['tax'] as num?)?.toDouble() ?? 0.0,
      deposit: (json['deposit'] as num?)?.toDouble() ?? 0.0,
      paidTotal: (json['paid_total'] as num).toDouble(),
      eventType: json['event_type'] as String,
      storeTier: (json['store_tier'] as String?) ?? 'A',
      storeRating: (json['store_rating'] as num?)?.toDouble() ?? 5.0,
      brandTier: (json['brand_tier'] as String?) ?? 'A',
      brandRating: (json['brand_rating'] as num?)?.toDouble() ?? 5.0,
      productTier: (json['product_tier'] as String?) ?? 'A',
      productRating: (json['product_rating'] as num?)?.toDouble() ?? 5.0,
      availability: (json['availability'] as String?) ?? 'in_stock',
      notes: (json['notes'] as String?) ?? '',
      recordedAt: json['recorded_at'] as String?,
      account: (json['account'] as String?) ?? 'default:checking',
    );
  }

  ReceiptEntryModel copyWith({
    String? entryId,
    bool? isSynced,
    String? syncedAt,
    String? receiptId,
    String? receiptDate,
    String? merchant,
    String? item,
    String? brand,
    String? category,
    double? quantity,
    double? packSize,
    String? unit,
    double? unitPrice,
    String? currency,
    double? discount,
    double? fee,
    double? tax,
    double? deposit,
    double? paidTotal,
    String? eventType,
    String? storeTier,
    double? storeRating,
    String? brandTier,
    double? brandRating,
    String? productTier,
    double? productRating,
    String? availability,
    String? notes,
    String? recordedAt,
    String? account,
  }) {
    return ReceiptEntryModel(
      entryId: entryId ?? this.entryId,
      isSynced: isSynced ?? this.isSynced,
      syncedAt: syncedAt ?? this.syncedAt,
      receiptId: receiptId ?? this.receiptId,
      receiptDate: receiptDate ?? this.receiptDate,
      merchant: merchant ?? this.merchant,
      item: item ?? this.item,
      brand: brand ?? this.brand,
      category: category ?? this.category,
      quantity: quantity ?? this.quantity,
      packSize: packSize ?? this.packSize,
      unit: unit ?? this.unit,
      unitPrice: unitPrice ?? this.unitPrice,
      currency: currency ?? this.currency,
      discount: discount ?? this.discount,
      fee: fee ?? this.fee,
      tax: tax ?? this.tax,
      deposit: deposit ?? this.deposit,
      paidTotal: paidTotal ?? this.paidTotal,
      eventType: eventType ?? this.eventType,
      storeTier: storeTier ?? this.storeTier,
      storeRating: storeRating ?? this.storeRating,
      brandTier: brandTier ?? this.brandTier,
      brandRating: brandRating ?? this.brandRating,
      productTier: productTier ?? this.productTier,
      productRating: productRating ?? this.productRating,
      availability: availability ?? this.availability,
      notes: notes ?? this.notes,
      recordedAt: recordedAt ?? this.recordedAt,
      account: account ?? this.account,
    );
  }
}
