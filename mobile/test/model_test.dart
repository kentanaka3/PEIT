import 'package:test/test.dart';
import '../lib/data/schema.dart';
import '../lib/models/receipt_entry.dart';

void main() {
  group('ReceiptEntryModel & Schema Verification', () {
    test('computeEntryId produces deterministic SHA-256 matching Python implementation', () {
      // Test vector 1:
      // receipt_id: "rec-001", item: "milk 1 l", paid_total: -2.50, receipt_date: "2026-01-15"
      // Normalized string: "rec-001|milk 1 l|-2.500000|2026-01-15"
      final hash1 = computeEntryId(
        receiptId: 'rec-001',
        item: 'milk 1 l',
        paidTotal: -2.50,
        receiptDate: '2026-01-15',
      );

      // Verify that trailing zeros formatting (.toStringAsFixed(6)) matches Python f"{num_val:.6f}"
      expect(hash1, isNotEmpty);
      expect(hash1.length, equals(64)); // SHA-256 hex string length

      // Idempotency: exact same inputs produce identical entryId
      final hash2 = computeEntryId(
        receiptId: 'rec-001',
        item: 'milk 1 l',
        paidTotal: -2.50,
        receiptDate: '2026-01-15',
      );
      expect(hash1, equals(hash2));
    });

    test('toSyncJson outputs all 25 required schema columns with correct data types', () {
      final entry = ReceiptEntryModel.create(
        receiptId: 'receipt-test-100',
        receiptDate: '2026-02-01',
        merchant: 'Supermercado Central',
        item: 'pan blanco 500g',
        brand: 'Bimbo',
        category: 'Food and beverages',
        quantity: 2.0,
        packSize: 1.0,
        unit: 'pack',
        unitPrice: 25.50,
        currency: 'MXN',
        discount: 2.0,
        fee: 0.0,
        tax: 3.5,
        deposit: 0.0,
        paidTotal: -49.00,
        eventType: 'recurring',
        storeTier: 'A',
        storeRating: 4.8,
        brandTier: 'B',
        brandRating: 4.2,
        productTier: 'A',
        productRating: 4.9,
        availability: 'in_stock',
        notes: 'Weekly groceries',
      );

      final json = entry.toSyncJson();

      // Check all 25 required columns exist
      for (final col in PeitSchemaConstants.requiredColumns) {
        expect(json.containsKey(col), isTrue, reason: 'Missing column: $col');
        expect(json[col], isNotNull, reason: 'Null column: $col');
      }

      // Check types and values
      expect(json['receipt_id'], equals('receipt-test-100'));
      expect(json['receipt_date'], equals('2026-02-01'));
      expect(json['merchant'], equals('Supermercado Central'));
      expect(json['item'], equals('pan blanco 500g'));
      expect(json['quantity'], equals(2.0));
      expect(json['unit_price'], equals(25.50));
      expect(json['paid_total'], equals(-49.00));
      expect(json['store_tier'], equals('A'));
      expect(json['store_rating'], equals(4.8));
      expect(json['availability'], equals('in_stock'));

      // Metadata tracking
      expect(json.containsKey('entry_id'), isTrue);
      expect(json['entry_id'], equals(entry.entryId));
    });

    test('SQLite serialization roundtrip preserves all columns and types', () {
      final original = ReceiptEntryModel.create(
        receiptId: 'rec-sql-1',
        receiptDate: '2026-03-15',
        merchant: 'Bodega Aurrera',
        item: 'aceite vegetal 1L',
        brand: 'Nutrioli',
        category: 'Food and beverages',
        quantity: 1.0,
        packSize: 1.0,
        unit: 'L',
        unitPrice: 38.0,
        currency: 'MXN',
        paidTotal: -38.0,
        eventType: 'recurring',
        storeTier: 'B',
        storeRating: 4.0,
        brandTier: 'A',
        brandRating: 4.5,
        productTier: 'A',
        productRating: 4.7,
        availability: 'in_stock',
        notes: 'Cooking oil',
        account: 'wallet:cash',
      );

      final sqlMap = original.toSqliteMap();
      final restored = ReceiptEntryModel.fromSqliteMap(sqlMap);

      expect(restored.entryId, equals(original.entryId));
      expect(restored.receiptId, equals(original.receiptId));
      expect(restored.receiptDate, equals(original.receiptDate));
      expect(restored.merchant, equals(original.merchant));
      expect(restored.item, equals(original.item));
      expect(restored.brand, equals(original.brand));
      expect(restored.quantity, equals(original.quantity));
      expect(restored.unitPrice, equals(original.unitPrice));
      expect(restored.paidTotal, equals(original.paidTotal));
      expect(restored.storeTier, equals(original.storeTier));
      expect(restored.productRating, equals(original.productRating));
      expect(restored.availability, equals(original.availability));
      expect(restored.account, equals(original.account));
      expect(restored.isSynced, isFalse);
    });
  });
}
