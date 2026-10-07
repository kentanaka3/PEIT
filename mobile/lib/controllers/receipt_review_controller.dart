/// Reactive state controller for reviewing parsed receipt items.
/// Powers both Card Stream (Mode 1) and Financial Data Grid (Mode 2).
library peit_receipt_review_controller;

import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import '../data/database.dart';
import '../data/schema.dart';
import '../models/receipt_entry.dart';
import '../ocr/models.dart';

class ReceiptReviewItem {
  final String tempId;
  ParsedLineItem parsed;
  Uint8List? snippetBytes;
  bool isUserModified;

  ReceiptReviewItem({
    required this.tempId,
    required this.parsed,
    this.snippetBytes,
    this.isUserModified = false,
  });

  bool get isHighConfidence => parsed.confidence >= 0.95;
}

class ReceiptReviewController extends ChangeNotifier {
  final String receiptId;
  final String receiptDate;
  final String merchant;
  final String currency;
  final double detectedPaidTotal;
  final double detectedSubtotal;
  final double detectedDiscountTotal;
  final double detectedTaxTotal;
  final double detectedFeeTotal;
  final double detectedDepositTotal;
  final String rawText;

  final List<ReceiptReviewItem> _items = [];
  final Set<String> _approvedIds = {};
  final Set<String> _discardedIds = {};
  int _activeRowIndex = 0;
  bool _isCommitting = false;

  ReceiptReviewController({
    required this.receiptId,
    required this.receiptDate,
    required this.merchant,
    required this.currency,
    required this.detectedPaidTotal,
    this.detectedSubtotal = 0.0,
    this.detectedDiscountTotal = 0.0,
    this.detectedTaxTotal = 0.0,
    this.detectedFeeTotal = 0.0,
    this.detectedDepositTotal = 0.0,
    this.rawText = '',
    List<ParsedLineItem> initialItems = const [],
  }) {
    for (int i = 0; i < initialItems.length; i++) {
      _items.add(ReceiptReviewItem(
        tempId: 'item-$i',
        parsed: initialItems[i],
      ));
    }
  }

  /// Create controller from a ParsedReceipt
  factory ReceiptReviewController.fromParsedReceipt(ParsedReceipt receipt) {
    return ReceiptReviewController(
      receiptId: receipt.receiptId,
      receiptDate: receipt.receiptDate,
      merchant: receipt.merchant,
      currency: receipt.currency,
      detectedPaidTotal: receipt.paidTotal,
      detectedSubtotal: receipt.subtotal,
      detectedDiscountTotal: receipt.discountTotal,
      detectedTaxTotal: receipt.taxTotal,
      detectedFeeTotal: receipt.feeTotal,
      detectedDepositTotal: receipt.depositTotal,
      rawText: receipt.rawText,
      initialItems: receipt.items,
    );
  }

  List<ReceiptReviewItem> get items => List.unmodifiable(_items);
  Set<String> get approvedIds => Set.unmodifiable(_approvedIds);
  Set<String> get discardedIds => Set.unmodifiable(_discardedIds);
  int get activeRowIndex => _activeRowIndex;
  bool get isCommitting => _isCommitting;

  ReceiptReviewItem? get activeItem =>
      _items.isNotEmpty && _activeRowIndex < _items.length ? _items[_activeRowIndex] : null;

  /// Items that are not discarded
  List<ReceiptReviewItem> get activeItems =>
      _items.where((i) => !_discardedIds.contains(i.tempId)).toList();

  /// Items that have been approved
  List<ReceiptReviewItem> get approvedItemsList =>
      _items.where((i) => _approvedIds.contains(i.tempId)).toList();

  /// Sum of total_price of all approved items
  double get calculatedApprovedSum => approvedItemsList.fold(
      0.0, (acc, item) => acc + item.parsed.totalPrice);

  /// Running sum of all active (non-discarded) items
  double get calculatedTotal => activeItems.fold(
      0.0, (acc, item) => acc + item.parsed.totalPrice);

  /// Target paid_total from receipt
  double get detectedTotal => detectedPaidTotal;

  /// Balance delta between running active items and detected total
  double get balanceDelta =>
      double.parse((calculatedTotal - detectedPaidTotal).abs().toStringAsFixed(2));

  /// True if running total matches detected total within 5 cents
  bool get isBalanced => balanceDelta < 0.05;

  void setActiveRowIndex(int index) {
    if (index >= 0 && index < _items.length && _activeRowIndex != index) {
      _activeRowIndex = index;
      notifyListeners();
    }
  }

  /// Attach pre-cropped snippet bytes to items by temporary ID
  void attachSnippetBytes(Map<String, Uint8List> snippets) {
    for (final item in _items) {
      if (snippets.containsKey(item.tempId)) {
        item.snippetBytes = snippets[item.tempId];
      }
    }
    notifyListeners();
  }

  /// Approve an item (Swipe Right or Checkbox)
  void approveItem(String tempId) {
    _discardedIds.remove(tempId);
    _approvedIds.add(tempId);
    notifyListeners();
  }

  /// Discard an item (Swipe Left or Delete)
  void discardItem(String tempId) {
    _approvedIds.remove(tempId);
    _discardedIds.add(tempId);
    notifyListeners();
  }

  /// Reset an item to pending review
  void unapproveItem(String tempId) {
    _approvedIds.remove(tempId);
    _discardedIds.remove(tempId);
    notifyListeners();
  }

  /// Bulk approve all items with confidence >= threshold (defaults to 0.95)
  void bulkApproveHighConfidence({double threshold = 0.95}) {
    for (final item in _items) {
      if (!_discardedIds.contains(item.tempId) && item.parsed.confidence >= threshold) {
        _approvedIds.add(item.tempId);
      }
    }
    notifyListeners();
  }

  /// Approve all remaining active items
  void approveAllActive() {
    for (final item in activeItems) {
      _approvedIds.add(item.tempId);
    }
    notifyListeners();
  }

  /// Update a specific field of an item
  void updateItemField(int index, String key, dynamic value) {
    if (index < 0 || index >= _items.length) return;
    final item = _items[index];
    item.isUserModified = true;

    switch (key) {
      case 'item':
        item.parsed.item = value as String;
        break;
      case 'brand':
        item.parsed.brand = value as String;
        break;
      case 'category':
        item.parsed.category = value as String;
        break;
      case 'quantity':
        item.parsed.quantity = (value as num).toDouble();
        break;
      case 'packSize':
      case 'pack_size':
        item.parsed.packSize = (value as num).toDouble();
        break;
      case 'unit':
        item.parsed.unit = value as String;
        break;
      case 'unitPrice':
      case 'unit_price':
        item.parsed.unitPrice = (value as num).toDouble();
        break;
      case 'totalPrice':
      case 'total_price':
        item.parsed.totalPrice = (value as num).toDouble();
        break;
      case 'discount':
        item.parsed.discount = (value as num).toDouble();
        break;
      case 'fee':
        item.parsed.fee = (value as num).toDouble();
        break;
      case 'tax':
        item.parsed.tax = (value as num).toDouble();
        break;
      case 'deposit':
        item.parsed.deposit = (value as num).toDouble();
        break;
      case 'storeTier':
      case 'store_tier':
        item.parsed.storeTier = value as String;
        break;
      case 'productTier':
      case 'product_tier':
        item.parsed.productTier = value as String;
        break;
      case 'availability':
        item.parsed.availability = value as String;
        break;
      case 'notes':
        item.parsed.notes = value as String;
        break;
    }

    notifyListeners();
  }

  /// Auto-recalculate total_price from quantity * unit_price
  void autoCalculateTotalPrice(int index) {
    if (index < 0 || index >= _items.length) return;
    final it = _items[index].parsed;
    it.totalPrice = double.parse((it.quantity * it.unitPrice).toStringAsFixed(2));
    _items[index].isUserModified = true;
    notifyListeners();
  }

  /// Auto-recalculate unit_price from total_price / (quantity * pack_size)
  void autoCalculateUnitPrice(int index) {
    if (index < 0 || index >= _items.length) return;
    final it = _items[index].parsed;
    final denom = it.quantity * it.packSize;
    if (denom > 0) {
      it.unitPrice = double.parse((it.totalPrice / denom).toStringAsFixed(2));
      _items[index].isUserModified = true;
      notifyListeners();
    }
  }

  /// Merge an item's description into the preceding line item and discard the current item
  void mergeWithPrevious(int index) {
    if (index <= 0 || index >= _items.length) return;
    final prev = _items[index - 1];
    final curr = _items[index];

    prev.parsed.item = '${prev.parsed.item} ${curr.parsed.item}'.trim();
    prev.parsed.notes = '${prev.parsed.notes}; merged(${curr.parsed.item})'.trim();
    prev.isUserModified = true;

    discardItem(curr.tempId);
    notifyListeners();
  }

  /// Apply one-tap reconciliation shortcut:
  /// Creates an adjustment item (e.g. Rounding / Deposit / Tax) to balance delta to zero
  void reconcileBalance({String reason = 'Rounding Adjustment'}) {
    final delta = detectedPaidTotal - calculatedTotal;
    if (delta.abs() < 0.01) return;

    final adjustmentItem = ParsedLineItem(
      item: reason,
      brand: 'Adjustment',
      category: 'General',
      quantity: 1.0,
      pack_size: 1.0,
      unit: 'ea',
      unitPrice: double.parse(delta.toStringAsFixed(2)),
      totalPrice: double.parse(delta.toStringAsFixed(2)),
      confidence: 1.0,
      notes: 'Auto-reconciled to balance receipt total',
    );

    final newTempId = 'item-reconcile-${DateTime.now().millisecondsSinceEpoch}';
    final reviewItem = ReceiptReviewItem(
      tempId: newTempId,
      parsed: adjustmentItem,
      isUserModified: true,
    );

    _items.add(reviewItem);
    _approvedIds.add(newTempId);
    notifyListeners();
  }

  /// Commit approved rows into Drift SQLite database inside an atomic transaction
  Future<int> commitToDatabase(AppDatabase db, {String account = 'default:checking'}) async {
    _isCommitting = true;
    notifyListeners();

    try {
      final toCommit = approvedItemsList.isNotEmpty ? approvedItemsList : activeItems;
      if (toCommit.isEmpty) return 0;

      final nowIso = DateTime.now().toUtc().toIso8601String();
      final List<ReceiptEntryModel> models = [];

      for (final item in toCommit) {
        final p = item.parsed;
        // Accounting sign convention: paid_total is negative for expenses
        final net = p.totalPrice - p.discount + p.tax + p.fee + p.deposit;
        final paidTot = net > 0 ? -net : (p.totalPrice > 0 ? -p.totalPrice : 0.0);

        final entryId = computeEntryId(
          receiptId: receiptId,
          item: p.item,
          paidTotal: paidTot,
          receiptDate: receiptDate,
        );

        models.add(ReceiptEntryModel(
          entryId: entryId,
          receiptId: receiptId,
          receiptDate: receiptDate,
          merchant: merchant,
          item: p.item,
          brand: p.brand.isNotEmpty ? p.brand : 'Generic',
          category: p.category.isNotEmpty ? p.category : 'General',
          quantity: p.quantity,
          packSize: p.packSize,
          unit: p.unit.isNotEmpty ? p.unit : 'ea',
          unitPrice: p.unitPrice,
          currency: currency,
          discount: p.discount.abs(),
          fee: -p.fee.abs(),
          tax: -p.tax.abs(),
          deposit: -p.deposit.abs(),
          paidTotal: double.parse(paidTot.toStringAsFixed(2)),
          eventType: p.eventType.isNotEmpty ? p.eventType : 'one_off',
          storeTier: PeitSchemaConstants.validTiers.contains(p.storeTier) ? p.storeTier : 'A',
          storeRating: p.storeRating,
          brandTier: PeitSchemaConstants.validTiers.contains(p.brandTier) ? p.brandTier : 'A',
          brandRating: p.brandRating,
          productTier: PeitSchemaConstants.validTiers.contains(p.productTier) ? p.productTier : 'A',
          productRating: p.productRating,
          availability: PeitSchemaConstants.availabilityStatuses.contains(p.availability)
              ? p.availability
              : 'in_stock',
          notes: p.notes,
          recordedAt: nowIso,
          account: account,
          isSynced: false,
        ));
      }

      db.insertEntries(models);
      return models.length;
    } finally {
      _isCommitting = false;
      notifyListeners();
    }
  }
}

