/// Canonical Single Source of Truth (SSOT) schema definitions for PEIT Mobile.
///
/// Mirrors `src/peit/schema.py` in pure Dart: canonical 25-column receipt schema,
/// ledger envelope columns, mobile sync attributes, domain enumerations,
/// cryptographic identity hashing with negative-zero clamping, and accounting
/// sign normalizers.
library peit_schema_constants;

import 'dart:convert';
import 'package:crypto/crypto.dart' show sha256;
import 'schema_constants.dart' as _root;

/// Schema version
const int schemaVersion = 1;

/// Canonical 25 receipt columns matching `config/receipt_schema.csv`.
const List<String> receiptColumns = [
  'receipt_id',
  'receipt_date',
  'merchant',
  'item',
  'brand',
  'category',
  'quantity',
  'pack_size',
  'unit',
  'unit_price',
  'currency',
  'discount',
  'fee',
  'tax',
  'deposit',
  'paid_total',
  'event_type',
  'store_tier',
  'store_rating',
  'brand_tier',
  'brand_rating',
  'product_tier',
  'product_rating',
  'availability',
  'notes',
];

/// Envelope attributes prepended/appended to canonical receipt rows in the ledger.
const List<String> ledgerEnvelopeColumns = [
  'entry_id',
  'month',
  'account',
  'recorded_at',
];

/// 29-column SQLite entries table projection and LedgerEntry order.
const List<String> ledgerColumns = [
  'entry_id',
  'month',
  'receipt_id',
  'receipt_date',
  'account',
  'merchant',
  'item',
  'brand',
  'category',
  'quantity',
  'pack_size',
  'unit',
  'unit_price',
  'currency',
  'discount',
  'fee',
  'tax',
  'deposit',
  'paid_total',
  'event_type',
  'store_tier',
  'store_rating',
  'brand_tier',
  'brand_rating',
  'product_tier',
  'product_rating',
  'availability',
  'notes',
  'recorded_at',
];

/// Mobile synchronization status columns.
const List<String> mobileSyncColumns = [
  'is_synced',
  'synced_at',
];

/// Permissible accounting transaction event types.
enum EventType {
  recurring('recurring'),
  oneOff('one_off'),
  transfer('transfer'),
  refund('refund'),
  income('income');

  final String value;
  const EventType(this.value);

  @override
  String toString() => value;
}

/// Permissible inventory availability statuses.
enum Availability {
  inStock('in_stock'),
  lowStock('low_stock'),
  outOfStock('out_of_stock'),
  discontinued('discontinued');

  final String value;
  const Availability(this.value);

  @override
  String toString() => value;
}

/// Permissible quality tiers for store, brand, and product ratings.
enum QualityTier {
  a('A'),
  b('B'),
  c('C'),
  d('D'),
  e('E');

  final String value;
  const QualityTier(this.value);

  @override
  String toString() => value;
}

/// Rating bounds
const double minRating = 1.0;
const double maxRating = 5.0;

/// Recognized currencies
const Set<String> recognizedCurrencies = {'MXN', 'USD', 'EUR', 'CAD'};

/// Cryptographic Identity Hashing
///
/// Computes deterministic SHA-256 hash for entry deduplication identical to
/// Python `compute_entry_id`:
/// `sha256(receipt_id|item|norm_amount|receipt_date)`
///
/// Includes negative-zero clamp safeguard:
/// `abs(num_val) == 0.0 -> 0.0`, formatted to 6 decimal places.
/// Strips whitespace from string components.
String computeEntryId({
  required String receiptId,
  required String item,
  required Object paidTotal,
  required String receiptDate,
}) {
  String normAmount;
  if (paidTotal is num) {
    final double numVal = paidTotal.abs() == 0.0 ? 0.0 : paidTotal.toDouble();
    normAmount = numVal.toStringAsFixed(6);
  } else {
    final parsed = double.tryParse(paidTotal.toString());
    if (parsed != null) {
      final double numVal = parsed.abs() == 0.0 ? 0.0 : parsed;
      normAmount = numVal.toStringAsFixed(6);
    } else {
      normAmount = paidTotal.toString().trim();
    }
  }

  final raw =
      '${receiptId.trim()}|${item.trim()}|$normAmount|${receiptDate.trim()}';
  final bytes = utf8.encode(raw);
  final digest = sha256.convert(bytes);
  return digest.toString();
}

/// Canonical accounting sign normalizers:
/// Ensures negative numeric sign for expenses (-abs(amount)).
double normalizeExpenseSign(num amount) => -amount.abs().toDouble();

/// Ensures positive numeric sign for income (+abs(amount)).
double normalizeIncomeSign(num amount) => amount.abs().toDouble();

/// Ensures negative numeric sign for surcharges (fees, taxes, deposits) (-abs(amount)).
double normalizeSurchargeSign(num amount) => -amount.abs().toDouble();

/// Ensures positive numeric magnitude for applied discounts (+abs(amount)).
double normalizeDiscountSign(num amount) => amount.abs().toDouble();

/// Backward compatibility class aliasing lists, sets, and functions for existing code.
class PeitSchemaConstants {
  static const int schemaVersion = _root.schemaVersion;

  static const List<String> requiredColumns = _root.receiptColumns;
  static const List<String> receiptColumns = _root.receiptColumns;
  static const List<String> ledgerEnvelopeColumns =
      _root.ledgerEnvelopeColumns;
  static const List<String> ledgerColumns = _root.ledgerColumns;
  static const List<String> mobileSyncColumns =
      _root.mobileSyncColumns;

  static const Set<String> eventTypes = {
    'recurring',
    'one_off',
    'transfer',
    'refund',
    'income',
  };

  static const Set<String> availabilityStatuses = {
    'in_stock',
    'low_stock',
    'out_of_stock',
    'discontinued',
  };

  static const Set<String> validTiers = {'A', 'B', 'C', 'D', 'E'};

  static const Set<String> recognizedCurrencies =
      _root.recognizedCurrencies;

  static const double minRating = _root.minRating;
  static const double maxRating = _root.maxRating;

  static String computeEntryId({
    required String receiptId,
    required String item,
    required Object paidTotal,
    required String receiptDate,
  }) =>
      _root.computeEntryId(
        receiptId: receiptId,
        item: item,
        paidTotal: paidTotal,
        receiptDate: receiptDate,
      );

  static double normalizeExpenseSign(num amount) =>
      _root.normalizeExpenseSign(amount);

  static double normalizeIncomeSign(num amount) =>
      _root.normalizeIncomeSign(amount);

  static double normalizeSurchargeSign(num amount) =>
      _root.normalizeSurchargeSign(amount);

  static double normalizeDiscountSign(num amount) =>
      _root.normalizeDiscountSign(amount);
}

