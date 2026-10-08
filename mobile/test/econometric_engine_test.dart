import 'package:test/test.dart';

import '../lib/data/database.dart';
import '../lib/models/receipt_entry.dart';
import '../lib/services/econometric_engine.dart';

void main() {
  group('EconometricEngine Pure Dart Unit Tests', () {
    test('single-month base data yields fixedBasketIndex = 100.0 and momPercent = null', () {
      final List<ReceiptEntryModel> entries = [
        ReceiptEntryModel.create(
          receiptId: 'r1',
          receiptDate: '2026-01-10',
          merchant: 'SuperMart',
          item: 'milk',
          category: 'Groceries',
          quantity: 2,
          unit: 'L',
          unitPrice: 20.0,
          paidTotal: -40.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r2',
          receiptDate: '2026-01-12',
          merchant: 'SuperMart',
          item: 'bread',
          category: 'Groceries',
          quantity: 1,
          unit: 'pc',
          unitPrice: 30.0,
          paidTotal: -30.0,
          eventType: 'one_off',
          currency: 'MXN',
        ),
      ];

      final results = EconometricEngine.calculateMonthlyIndices(entries);

      expect(results.length, equals(1));
      final base = results.first;
      expect(base.month, equals('2026-01'));
      expect(base.fixedBasketIndex, equals(100.0));
      expect(base.changingBasketExpenditureIndex, equals(100.0));
      expect(base.coveragePercent, equals(100.0));
      expect(base.momPercent, isNull);
      expect(base.expenditure, equals(70.0));
      expect(base.status, equals('derived'));
    });

    test('replicates Python test_indices_separate_price_and_expenditure calculation', () {
      // Python test vector from test/test_core.py:
      // row("2026-01", 2, -2) -> unit_price 2, paid -2
      // row("2026-02", 3, -6) -> unit_price 3, paid -6
      // result[1]["fixed_basket_index"] == 150.0
      // result[1]["changing_basket_expenditure_index"] == 300.0
      // result[1]["mom_percent"] == 50.0
      final List<ReceiptEntryModel> entries = [
        ReceiptEntryModel.create(
          receiptId: 'r1',
          receiptDate: '2026-01-15',
          merchant: 'm',
          item: 'milk',
          category: 'Food and beverages',
          quantity: 1,
          unit: 'L',
          unitPrice: 2.0,
          paidTotal: -2.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r2',
          receiptDate: '2026-02-15',
          merchant: 'm',
          item: 'milk',
          category: 'Food and beverages',
          quantity: 2,
          unit: 'L',
          unitPrice: 3.0,
          paidTotal: -6.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
      ];

      final results = EconometricEngine.calculateMonthlyIndices(entries);

      expect(results.length, equals(2));
      expect(results[0].month, equals('2026-01'));
      expect(results[0].fixedBasketIndex, equals(100.0));
      expect(results[0].changingBasketExpenditureIndex, equals(100.0));
      expect(results[0].momPercent, isNull);

      expect(results[1].month, equals('2026-02'));
      expect(results[1].fixedBasketIndex, equals(150.0));
      expect(results[1].changingBasketExpenditureIndex, equals(300.0));
      expect(results[1].momPercent, equals(50.0));
      expect(results[1].expenditure, equals(6.0));
    });

    test('replicates Python test_intra_month_duplicate_items_weighted_average', () {
      // Python test vector from test/test_core.py:
      // Base month:
      // 2 units of milk @ 20.00 and 1 unit of milk @ 26.00 ->
      // weighted price = (40 + 26) / 3 = 22.00
      // Month 2:
      // 1 unit of milk @ 33.00 ->
      // price index should be 100 * (33.00 / 22.00) = 150.0
      final List<ReceiptEntryModel> entries = [
        ReceiptEntryModel.create(
          receiptId: 'r1',
          receiptDate: '2026-01-05',
          merchant: 'm',
          item: 'milk',
          category: 'Food and beverages',
          quantity: 2,
          unit: 'L',
          unitPrice: 20.0,
          paidTotal: -40.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r2',
          receiptDate: '2026-01-15',
          merchant: 'm',
          item: 'milk',
          category: 'Food and beverages',
          quantity: 1,
          unit: 'L',
          unitPrice: 26.0,
          paidTotal: -26.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r3',
          receiptDate: '2026-02-10',
          merchant: 'm',
          item: 'milk',
          category: 'Food and beverages',
          quantity: 1,
          unit: 'L',
          unitPrice: 33.0,
          paidTotal: -33.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
      ];

      final results = EconometricEngine.calculateMonthlyIndices(entries);

      expect(results.length, equals(2));
      expect(results[0].fixedBasketIndex, equals(100.0));
      expect(results[1].fixedBasketIndex, equals(150.0));
      expect(results[1].momPercent, equals(50.0));
    });

    test('strictly excludes non-consumption entries (income, transfer, refund)', () {
      final List<ReceiptEntryModel> entries = [
        // Base month consumption
        ReceiptEntryModel.create(
          receiptId: 'r1',
          receiptDate: '2026-01-01',
          merchant: 'Store',
          item: 'bread',
          category: 'Food',
          quantity: 1,
          unit: 'pc',
          unitPrice: 10.0,
          paidTotal: -10.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
        // Non-consumption transactions in Base month
        ReceiptEntryModel.create(
          receiptId: 'r2',
          receiptDate: '2026-01-02',
          merchant: 'Employer',
          item: 'salary',
          category: 'Income',
          quantity: 1,
          unit: 'mo',
          unitPrice: 5000.0,
          paidTotal: 5000.0,
          eventType: 'income',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r3',
          receiptDate: '2026-01-03',
          merchant: 'Bank',
          item: 'transfer to savings',
          category: 'Financial',
          quantity: 1,
          unit: 'tx',
          unitPrice: 1000.0,
          paidTotal: -1000.0,
          eventType: 'transfer',
          currency: 'MXN',
        ),
        // Month 2 consumption
        ReceiptEntryModel.create(
          receiptId: 'r4',
          receiptDate: '2026-02-01',
          merchant: 'Store',
          item: 'bread',
          category: 'Food',
          quantity: 1,
          unit: 'pc',
          unitPrice: 12.0,
          paidTotal: -12.0,
          eventType: 'one_off',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r5',
          receiptDate: '2026-02-05',
          merchant: 'Store',
          item: 'store refund',
          category: 'Refund',
          quantity: 1,
          unit: 'tx',
          unitPrice: 50.0,
          paidTotal: 50.0,
          eventType: 'refund',
          currency: 'MXN',
        ),
      ];

      final results = EconometricEngine.calculateMonthlyIndices(entries);

      expect(results.length, equals(2));
      expect(results[0].expenditure, equals(10.0)); // salary & transfer excluded
      expect(results[1].expenditure, equals(12.0)); // refund excluded
      expect(results[0].fixedBasketIndex, equals(100.0));
      expect(results[1].fixedBasketIndex, equals(120.0));
      expect(results[1].momPercent, equals(20.0));
    });

    test('handles empty entries gracefully', () {
      final results = EconometricEngine.calculateMonthlyIndices([]);
      expect(results, isEmpty);
    });
  });

  group('Drift SQLite Database Econometric Aggregation Queries', () {
    late AppDatabase db;

    setUp(() {
      db = AppDatabase.openInMemory();
    });

    tearDown(() {
      db.close();
    });

    test('getMonthlyCashFlowKpis computes income, expenditure, transfers, refunds, and net balance', () async {
      final List<ReceiptEntryModel> entries = [
        ReceiptEntryModel.create(
          receiptId: 'rec-1',
          receiptDate: '2026-03-01',
          merchant: 'Employer',
          item: 'Salary',
          category: 'Income',
          quantity: 1,
          unit: 'mo',
          unitPrice: 3000.0,
          paidTotal: 3000.0,
          eventType: 'income',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'rec-2',
          receiptDate: '2026-03-05',
          merchant: 'RentCorp',
          item: 'Apartment Rent',
          category: 'Housing',
          quantity: 1,
          unit: 'mo',
          unitPrice: 1200.0,
          paidTotal: -1200.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'rec-3',
          receiptDate: '2026-03-10',
          merchant: 'SuperMart',
          item: 'Groceries',
          category: 'Food',
          quantity: 1,
          unit: 'cart',
          unitPrice: 350.0,
          paidTotal: -350.0,
          eventType: 'one_off',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'rec-4',
          receiptDate: '2026-03-15',
          merchant: 'Bank',
          item: 'Transfer to Brokerage',
          category: 'Financial',
          quantity: 1,
          unit: 'tx',
          unitPrice: 500.0,
          paidTotal: -500.0,
          eventType: 'transfer',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'rec-5',
          receiptDate: '2026-03-20',
          merchant: 'Store',
          item: 'Returned Item',
          category: 'Shopping',
          quantity: 1,
          unit: 'item',
          unitPrice: 50.0,
          paidTotal: 50.0,
          eventType: 'refund',
          currency: 'MXN',
        ),
        // February entry to test month filtering
        ReceiptEntryModel.create(
          receiptId: 'rec-6',
          receiptDate: '2026-02-28',
          merchant: 'Cafe',
          item: 'Coffee',
          category: 'Food',
          quantity: 1,
          unit: 'cup',
          unitPrice: 5.0,
          paidTotal: -5.0,
          eventType: 'one_off',
          currency: 'MXN',
        ),
      ];

      db.insertEntries(entries);

      // 1. Filtered by month 2026-03
      final marchKpis = await db.getMonthlyCashFlowKpis(month: '2026-03');
      expect(marchKpis.totalIncome, equals(3000.0));
      expect(marchKpis.totalExpenditure, equals(1550.0)); // 1200 + 350
      expect(marchKpis.netTransfers, equals(-500.0));
      expect(marchKpis.netRefunds, equals(50.0));
      expect(marchKpis.netBalance, equals(1000.0)); // 3000 - 1200 - 350 - 500 + 50
      expect(marchKpis.transactionCount, equals(5));

      // 2. All time KPIs
      final allKpis = await db.getMonthlyCashFlowKpis();
      expect(allKpis.totalIncome, equals(3000.0));
      expect(allKpis.totalExpenditure, equals(1555.0)); // 1550 + 5
      expect(allKpis.netBalance, equals(995.0));
      expect(allKpis.transactionCount, equals(6));
    });

    test('getCategoryBreakdown groups consumption entries and reconciles percentages', () async {
      final List<ReceiptEntryModel> entries = [
        ReceiptEntryModel.create(
          receiptId: 'r1',
          receiptDate: '2026-03-01',
          merchant: 'SuperMart',
          item: 'Groceries',
          category: 'Food',
          quantity: 1,
          unit: 'cart',
          unitPrice: 60.0,
          paidTotal: -60.0,
          eventType: 'recurring',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r2',
          receiptDate: '2026-03-02',
          merchant: 'Metro',
          item: 'Subway Card',
          category: 'Transport',
          quantity: 1,
          unit: 'card',
          unitPrice: 40.0,
          paidTotal: -40.0,
          eventType: 'one_off',
          currency: 'MXN',
        ),
        // Income should be excluded
        ReceiptEntryModel.create(
          receiptId: 'r3',
          receiptDate: '2026-03-03',
          merchant: 'Work',
          item: 'Bonus',
          category: 'Income',
          quantity: 1,
          unit: 'bonus',
          unitPrice: 500.0,
          paidTotal: 500.0,
          eventType: 'income',
          currency: 'MXN',
        ),
      ];

      db.insertEntries(entries);

      final breakdown = await db.getCategoryBreakdown(month: '2026-03');
      expect(breakdown.length, equals(2));
      expect(breakdown[0].category, equals('Food'));
      expect(breakdown[0].totalSpent, equals(60.0));
      expect(breakdown[0].percentage, equals(60.0));
      expect(breakdown[0].itemCount, equals(1));

      expect(breakdown[1].category, equals('Transport'));
      expect(breakdown[1].totalSpent, equals(40.0));
      expect(breakdown[1].percentage, equals(40.0));
      expect(breakdown[1].itemCount, equals(1));
    });

    test('getHistoricalMonths returns sorted unique YYYY-MM strings', () async {
      final List<ReceiptEntryModel> entries = [
        ReceiptEntryModel.create(
          receiptId: 'r1',
          receiptDate: '2026-03-15',
          merchant: 'A',
          item: 'item1',
          category: 'Cat',
          quantity: 1,
          unit: 'u',
          unitPrice: 10,
          paidTotal: -10,
          eventType: 'one_off',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r2',
          receiptDate: '2026-01-20',
          merchant: 'B',
          item: 'item2',
          category: 'Cat',
          quantity: 1,
          unit: 'u',
          unitPrice: 10,
          paidTotal: -10,
          eventType: 'one_off',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r3',
          receiptDate: '2026-02-10',
          merchant: 'C',
          item: 'item3',
          category: 'Cat',
          quantity: 1,
          unit: 'u',
          unitPrice: 10,
          paidTotal: -10,
          eventType: 'one_off',
          currency: 'MXN',
        ),
        ReceiptEntryModel.create(
          receiptId: 'r4',
          receiptDate: '2026-01-05',
          merchant: 'D',
          item: 'item4',
          category: 'Cat',
          quantity: 1,
          unit: 'u',
          unitPrice: 10,
          paidTotal: -10,
          eventType: 'one_off',
          currency: 'MXN',
        ),
      ];

      db.insertEntries(entries);

      final months = await db.getHistoricalMonths();
      expect(months, equals(['2026-01', '2026-02', '2026-03']));
    });
  });
}
