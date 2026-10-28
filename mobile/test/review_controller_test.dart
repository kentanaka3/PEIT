import 'package:test/test.dart';
import '../lib/controllers/receipt_review_controller.dart';
import '../lib/data/database.dart';
import '../lib/data/schema_constants.dart';
import '../lib/ocr/models.dart';

void main() {
  group('ReceiptReviewController & Hybrid Ledger Commit', () {
    test('Bulk approval of >95% confidence items marks eligible items as approved', () {
      final itemHigh1 = ParsedLineItem(
        item: 'LECHE ENTERA 1L',
        totalPrice: 26.00,
        unitPrice: 26.00,
        confidence: 0.98,
      );
      final itemHigh2 = ParsedLineItem(
        item: 'PAN BLANCO 500G',
        totalPrice: 45.00,
        unitPrice: 45.00,
        confidence: 0.96,
      );
      final itemLow = ParsedLineItem(
        item: 'PROMO DESC',
        totalPrice: 10.00,
        unitPrice: 10.00,
        confidence: 0.65,
      );

      final controller = ReceiptReviewController(
        receiptId: 'rcpt-test-01',
        receiptDate: '2026-10-06',
        merchant: 'Soriana',
        currency: 'MXN',
        detectedPaidTotal: 81.00,
        initialItems: [itemHigh1, itemHigh2, itemLow],
      );

      expect(controller.items.length, equals(3));
      expect(controller.approvedIds.isEmpty, isTrue);

      // Trigger bulk approval for threshold >= 0.95
      controller.bulkApproveHighConfidence(threshold: 0.95);

      expect(controller.approvedIds.length, equals(2));
      expect(controller.approvedIds.contains('item-0'), isTrue);
      expect(controller.approvedIds.contains('item-1'), isTrue);
      expect(controller.approvedIds.contains('item-2'), isFalse);
    });

    test('Field modifications and auto-recalculation update item and balance', () {
      final item = ParsedLineItem(
        item: 'MANZANAS',
        quantity: 2.0,
        unitPrice: 20.00,
        totalPrice: 30.00, // Intentional mismatch
      );

      final controller = ReceiptReviewController(
        receiptId: 'rcpt-test-02',
        receiptDate: '2026-10-06',
        merchant: 'Walmart',
        currency: 'MXN',
        detectedPaidTotal: 40.00,
        initialItems: [item],
      );

      expect(controller.isBalanced, isFalse);
      expect(controller.balanceDelta, equals(10.00));

      // Auto-recalculate total: 2.0 * 20.00 = 40.00
      controller.autoCalculateTotalPrice(0);

      expect(controller.items[0].parsed.totalPrice, equals(40.00));
      expect(controller.isBalanced, isTrue);
      expect(controller.balanceDelta, equals(0.00));
    });

    test('reconcileBalance shortcut adds adjustment row to achieve balance', () {
      final item = ParsedLineItem(
        item: 'SODA 600ML',
        totalPrice: 18.00,
        unitPrice: 18.00,
      );

      final controller = ReceiptReviewController(
        receiptId: 'rcpt-test-03',
        receiptDate: '2026-10-06',
        merchant: 'Oxxo',
        currency: 'MXN',
        detectedPaidTotal: 18.50, // 50 cents rounding / bag fee discrepancy
        initialItems: [item],
      );

      expect(controller.isBalanced, isFalse);

      controller.reconcileBalance(reason: 'Bag Fee');

      expect(controller.items.length, equals(2));
      expect(controller.items[1].parsed.item, equals('Bag Fee'));
      expect(controller.items[1].parsed.totalPrice, equals(0.50));
      expect(controller.isBalanced, isTrue);
    });

    test('commitToDatabase writes approved rows to SQLite with valid schema and deterministic entry_id', () async {
      final db = AppDatabase.openInMemory();

      try {
        final item1 = ParsedLineItem(
          item: 'QUESO PANELA 400G',
          brand: 'FUD',
          category: 'Food and beverages',
          quantity: 1.0,
          packSize: 1.0,
          unit: 'ea',
          unitPrice: 58.00,
          totalPrice: 58.00,
          confidence: 0.99,
        );

        final controller = ReceiptReviewController(
          receiptId: 'rcpt-commit-01',
          receiptDate: '2026-10-06',
          merchant: 'Chedraui',
          currency: 'MXN',
          detectedPaidTotal: 58.00,
          initialItems: [item1],
        );

        controller.approveItem('item-0');

        final count = await controller.commitToDatabase(db);
        expect(count, equals(1));

        final allEntries = db.getAllEntries();
        expect(allEntries.length, equals(1));

        final entry = allEntries.first;
        expect(entry.receiptId, equals('rcpt-commit-01'));
        expect(entry.merchant, equals('Chedraui'));
        expect(entry.item, equals('QUESO PANELA 400G'));
        expect(entry.brand, equals('FUD'));
        expect(entry.paidTotal, equals(-58.00)); // Expense negative
        expect(entry.isSynced, isFalse);

        // Verify deterministic hash matches computeEntryId
        final expectedHash = computeEntryId(
          receiptId: 'rcpt-commit-01',
          item: 'QUESO PANELA 400G',
          paidTotal: -58.00,
          receiptDate: '2026-10-06',
        );
        expect(entry.entryId, equals(expectedHash));
      } finally {
        db.close();
      }
    });
  });
}
