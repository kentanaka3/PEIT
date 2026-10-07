/// Mode 2: High-Density Financial Data Grid with Split Inspector Sheet.
/// Inspired by Bloomberg/Excel workstations with sticky split inspector sheet for active row.
library peit_receipt_data_grid_screen;

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../controllers/receipt_review_controller.dart';
import '../data/database.dart';
import 'receipt_card_stream_screen.dart';

class ReceiptDataGridScreen extends StatefulWidget {
  final ReceiptReviewController controller;
  final AppDatabase database;
  final String? imagePath;

  const ReceiptDataGridScreen({
    super.key,
    required this.controller,
    required this.database,
    this.imagePath,
  });

  @override
  State<ReceiptDataGridScreen> createState() => _ReceiptDataGridScreenState();
}

class _ReceiptDataGridScreenState extends State<ReceiptDataGridScreen> {
  final TextEditingController _itemEditController = TextEditingController();
  final TextEditingController _priceEditController = TextEditingController();
  final TextEditingController _qtyEditController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _syncEditControllers();
  }

  void _syncEditControllers() {
    final active = widget.controller.activeItem;
    if (active != null) {
      _itemEditController.text = active.parsed.item;
      _priceEditController.text = active.parsed.totalPrice.toStringAsFixed(2);
      _qtyEditController.text = active.parsed.quantity.toStringAsFixed(active.parsed.quantity % 1 == 0 ? 0 : 2);
    }
  }

  void _switchToCardStream() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => ReceiptCardStreamScreen(
          controller: widget.controller,
          database: widget.database,
          imagePath: widget.imagePath,
        ),
      ),
    );
  }

  Future<void> _commitAndFinish() async {
    final count = await widget.controller.commitToDatabase(widget.database);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Successfully committed $count items to PEIT SQLite ledger!'),
        backgroundColor: Colors.green.shade700,
      ),
    );
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;

    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final activeItem = controller.activeItem;
        final items = controller.activeItems;
        final isBalanced = controller.isBalanced;

        return Scaffold(
          appBar: AppBar(
            title: Text(
              '${controller.merchant} - Financial Grid',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.view_agenda),
                tooltip: 'Switch to Card Stream View',
                onPressed: _switchToCardStream,
              ),
              IconButton(
                icon: const Icon(Icons.select_all),
                tooltip: 'Approve All Items',
                onPressed: () {
                  HapticFeedback.lightImpact();
                  controller.approveAllActive();
                },
              ),
            ],
          ),
          body: Column(
            children: [
              // Sticky Tabular Header
              Container(
                color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.6),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: const Row(
                  children: [
                    SizedBox(width: 32, child: Text('ST', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                    SizedBox(width: 24, child: Text('#', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                    Expanded(flex: 5, child: Text('ITEM DESCRIPTION', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                    SizedBox(width: 36, child: Text('QTY', textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                    SizedBox(width: 36, child: Text('UNIT', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                    SizedBox(width: 60, child: Text('PRICE', textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                    SizedBox(width: 65, child: Text('TOTAL', textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11))),
                  ],
                ),
              ),

              // Scrollable High-Density Rows
              Expanded(
                flex: 6,
                child: ListView.separated(
                  itemCount: items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1, thickness: 0.5),
                  itemBuilder: (context, index) {
                    final item = items[index];
                    final isSelected = controller.activeRowIndex == index;
                    final isApproved = controller.approvedIds.contains(item.tempId);
                    final isMathOk = item.parsed.isMathValid;

                    return InkWell(
                      onTap: () {
                        controller.setActiveRowIndex(index);
                        _syncEditControllers();
                      },
                      child: Container(
                        color: isSelected
                            ? Theme.of(context).colorScheme.primary.withOpacity(0.12)
                            : (isApproved ? Colors.green.withOpacity(0.04) : Colors.transparent),
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                        child: Row(
                          children: [
                            // Status indicator
                            SizedBox(
                              width: 32,
                              child: Icon(
                                isApproved
                                    ? Icons.check_circle
                                    : (!isMathOk ? Icons.error_outline : Icons.radio_button_unchecked),
                                size: 16,
                                color: isApproved
                                    ? Colors.green
                                    : (!isMathOk ? Colors.red : Colors.grey),
                              ),
                            ),
                            // Index #
                            SizedBox(
                              width: 24,
                              child: Text(
                                '${index + 1}',
                                style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                              ),
                            ),
                            // Item name
                            Expanded(
                              flex: 5,
                              child: Text(
                                item.parsed.item,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                ),
                              ),
                            ),
                            // Quantity
                            SizedBox(
                              width: 36,
                              child: Text(
                                item.parsed.quantity.toStringAsFixed(item.parsed.quantity % 1 == 0 ? 0 : 1),
                                textAlign: TextAlign.right,
                                style: const TextStyle(fontSize: 12, fontFamily: 'monospace'),
                              ),
                            ),
                            // Unit
                            SizedBox(
                              width: 36,
                              child: Text(
                                item.parsed.unit,
                                textAlign: TextAlign.center,
                                style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
                              ),
                            ),
                            // Unit price
                            SizedBox(
                              width: 60,
                              child: Text(
                                item.parsed.unitPrice.toStringAsFixed(2),
                                textAlign: TextAlign.right,
                                style: const TextStyle(fontSize: 12, fontFamily: 'monospace'),
                              ),
                            ),
                            // Total price
                            SizedBox(
                              width: 65,
                              child: Text(
                                item.parsed.totalPrice.toStringAsFixed(2),
                                textAlign: TextAlign.right,
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  fontFamily: 'monospace',
                                  color: isMathOk ? null : Colors.red.shade700,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),

              const Divider(height: 2, thickness: 2),

              // Sticky Split Inspector Sheet for Active Row
              Expanded(
                flex: 4,
                child: activeItem == null
                    ? const Center(child: Text('Select a row to inspect'))
                    : Container(
                        color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.2),
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Inspector Header
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  'Active Row #${controller.activeRowIndex + 1}: ${activeItem.parsed.category}',
                                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                ),
                                Row(
                                  children: [
                                    ElevatedButton.icon(
                                      icon: const Icon(Icons.check, size: 14),
                                      label: const Text('Approve', style: TextStyle(fontSize: 11)),
                                      style: ElevatedButton.styleFrom(
                                        visualDensity: VisualDensity.compact,
                                        padding: const EdgeInsets.symmetric(horizontal: 8),
                                      ),
                                      onPressed: () => controller.approveItem(activeItem.tempId),
                                    ),
                                    const SizedBox(width: 6),
                                    OutlinedButton.icon(
                                      icon: const Icon(Icons.delete_outline, size: 14),
                                      label: const Text('Discard', style: TextStyle(fontSize: 11)),
                                      style: OutlinedButton.styleFrom(
                                        visualDensity: VisualDensity.compact,
                                        padding: const EdgeInsets.symmetric(horizontal: 8),
                                      ),
                                      onPressed: () => controller.discardItem(activeItem.tempId),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),

                            // Image Crop or Raw OCR Line
                            if (activeItem.snippetBytes != null)
                              Container(
                                height: 42,
                                width: double.infinity,
                                decoration: BoxDecoration(
                                  color: Colors.black87,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: ClipRRect(
                                  borderRadius: BorderRadius.circular(4),
                                  child: Image.memory(
                                    activeItem.snippetBytes!,
                                    fit: BoxFit.contain,
                                  ),
                                ),
                              )
                            else if (widget.imagePath != null && File(widget.imagePath!).existsSync())
                              Container(
                                height: 42,
                                width: double.infinity,
                                color: Colors.black87,
                                child: const Center(
                                  child: Text('Receipt crop region', style: TextStyle(color: Colors.white70, fontSize: 11)),
                                ),
                              ),

                            const SizedBox(height: 8),
                            // In-place Quick Editor
                            Row(
                              children: [
                                Expanded(
                                  flex: 4,
                                  child: TextField(
                                    controller: _itemEditController,
                                    decoration: const InputDecoration(
                                      labelText: 'Item Name',
                                      isDense: true,
                                      border: OutlineInputBorder(),
                                    ),
                                    style: const TextStyle(fontSize: 12),
                                    onChanged: (val) => controller.updateItemField(controller.activeRowIndex, 'item', val),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Expanded(
                                  flex: 2,
                                  child: TextField(
                                    controller: _qtyEditController,
                                    keyboardType: TextInputType.number,
                                    decoration: const InputDecoration(
                                      labelText: 'Qty',
                                      isDense: true,
                                      border: OutlineInputBorder(),
                                    ),
                                    style: const TextStyle(fontSize: 12),
                                    onChanged: (val) {
                                      final d = double.tryParse(val);
                                      if (d != null) {
                                        controller.updateItemField(controller.activeRowIndex, 'quantity', d);
                                      }
                                    },
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Expanded(
                                  flex: 2,
                                  child: TextField(
                                    controller: _priceEditController,
                                    keyboardType: TextInputType.number,
                                    decoration: const InputDecoration(
                                      labelText: 'Total',
                                      isDense: true,
                                      border: OutlineInputBorder(),
                                    ),
                                    style: const TextStyle(fontSize: 12),
                                    onChanged: (val) {
                                      final d = double.tryParse(val);
                                      if (d != null) {
                                        controller.updateItemField(controller.activeRowIndex, 'totalPrice', d);
                                      }
                                    },
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
              ),

              // Sticky Continuous Accounting Reconciliation Bar
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface,
                  border: Border(top: BorderSide(color: isBalanced ? Colors.green : Colors.amber.shade700, width: 2)),
                ),
                child: SafeArea(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Sum: \$${controller.calculatedTotal.toStringAsFixed(2)} | Target: \$${controller.detectedTotal.toStringAsFixed(2)}',
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                          ),
                          Text(
                            isBalanced ? 'Balanced (Δ = \$0.00)' : 'Discrepancy: \$${controller.balanceDelta.toStringAsFixed(2)}',
                            style: TextStyle(
                              fontSize: 11,
                              color: isBalanced ? Colors.green : Colors.red.shade700,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                      ElevatedButton(
                        onPressed: _commitAndFinish,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: isBalanced ? Colors.green.shade700 : null,
                          foregroundColor: isBalanced ? Colors.white : null,
                        ),
                        child: const Text('Commit Ledger'),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

