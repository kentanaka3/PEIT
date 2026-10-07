import 'dart:math' as math;
import '../models/receipt_entry.dart';

/// Data model representing a monthly price and expenditure index record.
/// Replicates the structure produced by `calculate_indices()` in `src/peit/core.py`.
class MonthlyIndexRecord {
  final String month; // YYYY-MM
  final double? fixedBasketIndex; // Base month = 100.0
  final double? changingBasketExpenditureIndex;
  final double coveragePercent;
  final double? momPercent; // Month-over-month percentage inflation
  final double expenditure;
  final String status;

  const MonthlyIndexRecord({
    required this.month,
    this.fixedBasketIndex,
    this.changingBasketExpenditureIndex,
    required this.coveragePercent,
    this.momPercent,
    required this.expenditure,
    this.status = 'derived',
  });

  MonthlyIndexRecord copyWith({
    String? month,
    double? fixedBasketIndex,
    double? changingBasketExpenditureIndex,
    double? coveragePercent,
    double? momPercent,
    double? expenditure,
    String? status,
  }) {
    return MonthlyIndexRecord(
      month: month ?? this.month,
      fixedBasketIndex: fixedBasketIndex ?? this.fixedBasketIndex,
      changingBasketExpenditureIndex:
          changingBasketExpenditureIndex ?? this.changingBasketExpenditureIndex,
      coveragePercent: coveragePercent ?? this.coveragePercent,
      momPercent: momPercent ?? this.momPercent,
      expenditure: expenditure ?? this.expenditure,
      status: status ?? this.status,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'month': month,
      'fixed_basket_index': fixedBasketIndex,
      'changing_basket_expenditure_index': changingBasketExpenditureIndex,
      'coverage_percent': coveragePercent,
      'mom_percent': momPercent,
      'expenditure': expenditure,
      'status': status,
    };
  }

  @override
  String toString() =>
      'MonthlyIndexRecord(month: $month, index: $fixedBasketIndex, mom: $momPercent%, exp: $expenditure)';
}

/// Helper container for internal price and quantity accumulation
class _ItemPriceAccumulator {
  double totalSpend = 0.0;
  double totalQuantity = 0.0;
}

/// Pure Dart Econometric Engine replicating `src/peit/core.py:calculate_indices()`.
class EconometricEngine {
  /// Computes quantity-weighted average unit price per item:
  /// $\bar{p}_{i,m} = \frac{\sum (q \cdot p)}{\sum q}$
  static Map<String, double> computeMonthlyItemUnitPrices(
      Iterable<ReceiptEntryModel> entries) {
    final accumulators = <String, _ItemPriceAccumulator>{};

    for (final entry in entries) {
      final qty = entry.quantity;
      final price = entry.unitPrice;
      final item = entry.item;

      if (qty > 0 && price >= 0) {
        final acc = accumulators.putIfAbsent(item, () => _ItemPriceAccumulator());
        acc.totalSpend += qty * price;
        acc.totalQuantity += qty;
      }
    }

    final result = <String, double>{};
    for (final entry in accumulators.entries) {
      if (entry.value.totalQuantity > 0) {
        result[entry.key] = entry.value.totalSpend / entry.value.totalQuantity;
      }
    }
    return result;
  }

  /// Calculates transparent monthly price and expenditure indices.
  ///
  /// Replicates `calculate_indices()` from `src/peit/core.py`:
  /// - Filters strictly on consumption entries (`event_type IN ('recurring', 'one_off')`).
  /// - Chronologically orders months (Base month is the first available month, indexed at 100.0).
  /// - Matched fixed basket formula:
  ///   $$I_m = 100.0 \times \frac{1}{|M_m|} \sum_{i \in M_m} \frac{\bar{p}_{i,m}}{\bar{p}_{i,0}}$$
  /// - Month-over-month inflation:
  ///   $$\text{MoM}_m = 100.0 \times \left(\frac{I_m}{I_{m-1}} - 1.0\right)$$
  static List<MonthlyIndexRecord> calculateMonthlyIndices(
      Iterable<ReceiptEntryModel> entries) {
    // 1. Group consumption transactions strictly by month (YYYY-MM)
    final grouped = <String, List<ReceiptEntryModel>>{};
    for (final entry in entries) {
      if (entry.eventType == 'recurring' || entry.eventType == 'one_off') {
        final dateStr = entry.receiptDate;
        if (dateStr.length >= 7) {
          final month = dateStr.substring(0, 7);
          grouped.putIfAbsent(month, () => []).add(entry);
        }
      }
    }

    final sortedMonths = grouped.keys.toList()..sort();
    if (sortedMonths.isEmpty) {
      return [];
    }

    // Base month = first chronological month
    final baseMonth = sortedMonths.first;
    final baseEntries = grouped[baseMonth]!;
    final basePrices = computeMonthlyItemUnitPrices(baseEntries);
    final baseTotalExpenditure = baseEntries.fold<double>(
      0.0,
      (sum, e) => sum + e.paidTotal.abs(),
    );

    final records = <MonthlyIndexRecord>[];

    for (final month in sortedMonths) {
      final currentEntries = grouped[month]!;
      final currentPrices = computeMonthlyItemUnitPrices(currentEntries);

      final matchedRatios = <double>[];
      for (final item in basePrices.keys) {
        final p0 = basePrices[item]!;
        final p1 = currentPrices[item];
        if (p1 != null && p0 > 0) {
          matchedRatios.add(p1 / p0);
        }
      }

      final double? fixedBasketIndex;
      if (matchedRatios.isNotEmpty) {
        final sumRatios = matchedRatios.fold<double>(0.0, (sum, r) => sum + r);
        fixedBasketIndex = _round(100.0 * (sumRatios / matchedRatios.length), 6);
      } else {
        fixedBasketIndex = null;
      }

      final currentExpenditure = currentEntries.fold<double>(
        0.0,
        (sum, e) => sum + e.paidTotal.abs(),
      );

      final double? changingBasketIndex;
      if (baseTotalExpenditure > 0) {
        changingBasketIndex = _round(100.0 * (currentExpenditure / baseTotalExpenditure), 6);
      } else {
        changingBasketIndex = null;
      }

      final double coveragePercent;
      if (basePrices.isNotEmpty) {
        coveragePercent = _round(100.0 * (matchedRatios.length / basePrices.length), 2);
      } else {
        coveragePercent = 0.0;
      }

      records.add(MonthlyIndexRecord(
        month: month,
        fixedBasketIndex: fixedBasketIndex,
        changingBasketExpenditureIndex: changingBasketIndex,
        coveragePercent: coveragePercent,
        expenditure: _round(currentExpenditure, 6),
        status: 'derived',
      ));
    }

    // 2. Compute Month-over-Month (MoM) inflation percentage
    final finalRecords = <MonthlyIndexRecord>[];
    for (int i = 0; i < records.length; i++) {
      final current = records[i];
      final currentIdx = current.fixedBasketIndex;
      final previousIdx = i > 0 ? records[i - 1].fixedBasketIndex : null;

      double? momPercent;
      if (i > 0 && currentIdx != null && previousIdx != null && previousIdx > 0) {
        momPercent = _round(100.0 * ((currentIdx / previousIdx) - 1.0), 6);
      }

      finalRecords.add(current.copyWith(momPercent: momPercent));
    }

    return finalRecords;
  }

  static double _round(double val, int places) {
    final mod = math.pow(10.0, places);
    return ((val * mod).roundToDouble()) / mod;
  }
}

