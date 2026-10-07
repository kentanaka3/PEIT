import 'package:test/test.dart';
import '../lib/data/schema_constants.dart';

void main() {
  group('Schema Constants & Canonical Specification', () {
    test('schemaVersion equals 1', () {
      expect(schemaVersion, equals(1));
      expect(PeitSchemaConstants.schemaVersion, equals(1));
    });

    test('receiptColumns has exactly 25 elements matching canonical order', () {
      expect(receiptColumns.length, equals(25));
      expect(PeitSchemaConstants.receiptColumns.length, equals(25));
      expect(PeitSchemaConstants.requiredColumns.length, equals(25));

      const expectedColumns = [
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

      expect(receiptColumns, equals(expectedColumns));
      expect(PeitSchemaConstants.receiptColumns, equals(expectedColumns));
    });

    test('ledgerColumns has exactly 29 elements with prefix and suffix envelopes', () {
      expect(ledgerColumns.length, equals(29));
      expect(PeitSchemaConstants.ledgerColumns.length, equals(29));
      expect(ledgerEnvelopeColumns.length, equals(4));

      expect(
        ledgerEnvelopeColumns,
        equals(['entry_id', 'month', 'account', 'recorded_at']),
      );

      // Verify prefix envelope
      expect(ledgerColumns[0], equals('entry_id'));
      expect(ledgerColumns[1], equals('month'));

      // Verify suffix envelope
      expect(ledgerColumns[28], equals('recorded_at'));

      // Verify all 25 receipt columns are contained within ledgerColumns
      for (final col in receiptColumns) {
        expect(ledgerColumns.contains(col), isTrue,
            reason: 'Missing receipt column in ledger: $col');
      }

      // Verify all ledgerEnvelopeColumns are contained within ledgerColumns
      for (final col in ledgerEnvelopeColumns) {
        expect(ledgerColumns.contains(col), isTrue,
            reason: 'Missing envelope column in ledger: $col');
      }
    });

    test('mobileSyncColumns contains sync attributes', () {
      expect(mobileSyncColumns.length, equals(2));
      expect(mobileSyncColumns, equals(['is_synced', 'synced_at']));
    });

    test('enum mappings for EventType, Availability, and QualityTier', () {
      // EventType
      expect(EventType.recurring.value, equals('recurring'));
      expect(EventType.oneOff.value, equals('one_off'));
      expect(EventType.transfer.value, equals('transfer'));
      expect(EventType.refund.value, equals('refund'));
      expect(EventType.income.value, equals('income'));
      expect(EventType.values.map((e) => e.value).toSet(),
          equals(PeitSchemaConstants.eventTypes));

      // Availability
      expect(Availability.inStock.value, equals('in_stock'));
      expect(Availability.lowStock.value, equals('low_stock'));
      expect(Availability.outOfStock.value, equals('out_of_stock'));
      expect(Availability.discontinued.value, equals('discontinued'));
      expect(Availability.values.map((a) => a.value).toSet(),
          equals(PeitSchemaConstants.availabilityStatuses));

      // QualityTier
      expect(QualityTier.a.value, equals('A'));
      expect(QualityTier.b.value, equals('B'));
      expect(QualityTier.c.value, equals('C'));
      expect(QualityTier.d.value, equals('D'));
      expect(QualityTier.e.value, equals('E'));
      expect(QualityTier.values.map((q) => q.value).toSet(),
          equals(PeitSchemaConstants.validTiers));
    });

    test('rating bounds and recognized currencies', () {
      expect(minRating, equals(1.0));
      expect(maxRating, equals(5.0));
      expect(recognizedCurrencies, equals({'MXN', 'USD', 'EUR', 'CAD'}));
      expect(PeitSchemaConstants.recognizedCurrencies,
          equals({'MXN', 'USD', 'EUR', 'CAD'}));
    });

    test('computeEntryId hash consistency with Python test vectors', () {
      // Vector 1 (test_ledger.py / test_schema.py)
      // "rec-01|milk 1 l|-2.500000|2026-01-15"
      final h1 = computeEntryId(
        receiptId: 'rec-01',
        item: 'milk 1 l',
        paidTotal: -2.5,
        receiptDate: '2026-01-15',
      );
      final h2 = computeEntryId(
        receiptId: 'rec-01',
        item: 'milk 1 l',
        paidTotal: '-2.50',
        receiptDate: '2026-01-15',
      );
      final h3 = computeEntryId(
        receiptId: 'rec-01',
        item: 'milk 1 l',
        paidTotal: -2.500000,
        receiptDate: '2026-01-15',
      );
      expect(h1, equals(h2));
      expect(h2, equals(h3));
      expect(h1.length, equals(64));

      // Vector 2: test_mobile_sync vectors
      expect(
        computeEntryId(
          receiptId: 'rec-001',
          item: 'milk 1 l',
          paidTotal: -2.50,
          receiptDate: '2026-01-15',
        ),
        equals('90b55482be333df935738569bf6eff4180c6f5fa9d8b265dab3bca3f700c97f1'),
      );
      expect(
        computeEntryId(
          receiptId: 'rec-004',
          item: 'salary payment',
          paidTotal: 15000.0,
          receiptDate: '2026-04-01',
        ),
        equals('ff99bb83a577f8691107e2e939b49207de0b11bf335665a3ed8fef8a72a37fc2'),
      );
    });

    test('negative-zero clamping produces identical hash to positive zero', () {
      final hNegZero = computeEntryId(
        receiptId: 'r1',
        item: 'sample item',
        paidTotal: -0.0,
        receiptDate: '2026-01-01',
      );
      final hPosZero = computeEntryId(
        receiptId: 'r1',
        item: 'sample item',
        paidTotal: 0.0,
        receiptDate: '2026-01-01',
      );
      final hStrZero = computeEntryId(
        receiptId: 'r1',
        item: 'sample item',
        paidTotal: '0',
        receiptDate: '2026-01-01',
      );
      final hIntZero = computeEntryId(
        receiptId: 'r1',
        item: 'sample item',
        paidTotal: 0,
        receiptDate: '2026-01-01',
      );

      expect(hNegZero, equals(hPosZero));
      expect(hNegZero, equals(hStrZero));
      expect(hNegZero, equals(hIntZero));

      // Matches Python sha256(b"r1|sample item|0.000000|2026-01-01")
      // Vector: 2b4e8d7009cc014ecbf3a7886f7dbcc493975fceadd64acf3c0ae63824b9f1a3
      expect(hNegZero,
          equals('2b4e8d7009cc014ecbf3a7886f7dbcc493975fceadd64acf3c0ae63824b9f1a3'));
    });

    test('accounting sign normalizers enforce domain invariants', () {
      // Expenses must be negative (-abs)
      expect(normalizeExpenseSign(25.50), equals(-25.50));
      expect(normalizeExpenseSign(-25.50), equals(-25.50));
      expect(normalizeExpenseSign(0.0), equals(0.0));

      // Income must be positive (+abs)
      expect(normalizeIncomeSign(1500.0), equals(1500.0));
      expect(normalizeIncomeSign(-1500.0), equals(1500.0));
      expect(normalizeIncomeSign(0.0), equals(0.0));

      // Surcharges (taxes, fees, deposits) must be negative (-abs)
      expect(normalizeSurchargeSign(2.5), equals(-2.5));
      expect(normalizeSurchargeSign(-2.5), equals(-2.5));
      expect(normalizeSurchargeSign(0.0), equals(0.0));

      // Discounts must be positive (+abs)
      expect(normalizeDiscountSign(5.0), equals(5.0));
      expect(normalizeDiscountSign(-5.0), equals(5.0));
      expect(normalizeDiscountSign(0.0), equals(0.0));
    });

    test('PeitSchemaConstants class aliases methods and constants', () {
      expect(
        PeitSchemaConstants.normalizeExpenseSign(10),
        equals(normalizeExpenseSign(10)),
      );
      expect(
        PeitSchemaConstants.normalizeIncomeSign(-10),
        equals(normalizeIncomeSign(-10)),
      );
      expect(
        PeitSchemaConstants.normalizeSurchargeSign(5),
        equals(normalizeSurchargeSign(5)),
      );
      expect(
        PeitSchemaConstants.normalizeDiscountSign(-5),
        equals(normalizeDiscountSign(-5)),
      );
      expect(
        PeitSchemaConstants.computeEntryId(
          receiptId: 'r',
          item: 'i',
          paidTotal: -0.0,
          receiptDate: '2026-01-01',
        ),
        equals(computeEntryId(
          receiptId: 'r',
          item: 'i',
          paidTotal: 0.0,
          receiptDate: '2026-01-01',
        )),
      );
    });
  });
}

