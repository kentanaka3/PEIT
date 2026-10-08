/// Mode 1: Mobile Phone One-Handed Swipe Card Stream Screen.
/// Provides snippet preview, field chips, sticky balance HUD, bulk approval, and rapid gestures.
library peit_receipt_card_stream_screen;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../controllers/receipt_review_controller.dart';
import '../data/database.dart';
import '../web_interop.dart';
import 'receipt_data_grid_screen.dart';

class ReceiptCardStreamScreen extends StatefulWidget {
  final ReceiptReviewController controller;
  final AppDatabase database;
  final String? imagePath;

  const ReceiptCardStreamScreen({
    super.key,
    required this.controller,
    required this.database,
    this.imagePath,
  });

  @override
  State<ReceiptCardStreamScreen> createState() => _ReceiptCardStreamScreenState();
}

class _ReceiptCardStreamScreenState extends State<ReceiptCardStreamScreen> {
  String _filter = 'all'; // 'all', 'pending', 'approved'

  List<ReceiptReviewItem> _getFilteredItems() {
    final c = widget.controller;
    if (_filter == 'pending') {
      return c.items.where((i) => !c.approvedIds.contains(i.tempId) && !c.discardedIds.contains(i.tempId)).toList();
    } else if (_filter == 'approved') {
      return c.items.where((i) => c.approvedIds.contains(i.tempId)).toList();
    }
    return c.activeItems;
  }

  void _switchToGrid() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => ReceiptDataGridScreen(
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

    // Web Interop notification if running inside an embedded web island
    try {
      WebInteropService().notifyEntryCommitted({
        'receipt_id': widget.controller.receiptId,
        'count': count,
        'merchant': widget.controller.merchant,
      });
    } catch (_) {}

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Successfully committed $count items to PEIT SQLite ledger!'),
        backgroundColor: Colors.green.shade700,
      ),
    );
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;

    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final items = _getFilteredItems();
        final isBalanced = controller.isBalanced;

        return Scaffold(
          appBar: AppBar(
            title: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  controller.merchant,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                Text(
                  '${controller.receiptDate} • ${controller.items.length} items',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade400),
                ),
              ],
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.table_chart),
                tooltip: 'Switch to Financial Data Grid',
                onPressed: _switchToGrid,
              ),
              IconButton(
                icon: const Icon(Icons.flash_on),
                tooltip: 'Bulk Approve >95% Confidence',
                onPressed: () {
                  HapticFeedback.mediumImpact();
                  controller.bulkApproveHighConfidence();
                },
              ),
            ],
          ),
          body: Stack(
            children: [
              Column(
                children: [
                  // Filter Chips Bar
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.3),
                    child: Row(
                      children: [
                        FilterChip(
                          label: Text('All (${controller.activeItems.length})'),
                          selected: _filter == 'all',
                          onSelected: (_) => setState(() => _filter = 'all'),
                        ),
                        const SizedBox(width: 8),
                        FilterChip(
                          label: Text('Pending (${controller.activeItems.length - controller.approvedIds.length})'),
                          selected: _filter == 'pending',
                          onSelected: (_) => setState(() => _filter = 'pending'),
                        ),
                        const SizedBox(width: 8),
                        FilterChip(
                          label: Text('Approved (${controller.approvedIds.length})'),
                          selected: _filter == 'approved',
                          onSelected: (_) => setState(() => _filter = 'approved'),
                        ),
                      ],
                    ),
                  ),

                  // Cards List
                  Expanded(
                    child: items.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(24.0),
                              child: Text(
                                _filter == 'pending'
                                    ? 'All active items have been reviewed!'
                                    : 'No items in this filter view.',
                                style: const TextStyle(fontSize: 15, color: Colors.grey),
                              ),
                            ),
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.only(top: 8, bottom: 130, left: 12, right: 12),
                            itemCount: items.length,
                            itemBuilder: (context, index) {
                              final item = items[index];
                              final isApproved = controller.approvedIds.contains(item.tempId);

                              return Dismissible(
                                key: ValueKey(item.tempId),
                                direction: DismissDirection.horizontal,
                                background: Container(
                                  margin: const EdgeInsets.symmetric(vertical: 6),
                                  decoration: BoxDecoration(
                                    color: Colors.green.shade600,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  alignment: Alignment.centerLeft,
                                  padding: const EdgeInsets.symmetric(horizontal: 24),
                                  child: const Row(
                                    children: [
                                      Icon(Icons.check_circle, color: Colors.white, size: 28),
                                      SizedBox(width: 8),
                                      Text('Approve', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                    ],
                                  ),
                                ),
                                secondaryBackground: Container(
                                  margin: const EdgeInsets.symmetric(vertical: 6),
                                  decoration: BoxDecoration(
                                    color: Colors.red.shade600,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  alignment: Alignment.centerRight,
                                  padding: const EdgeInsets.symmetric(horizontal: 24),
                                  child: const Row(
                                    mainAxisAlignment: MainAxisAlignment.end,
                                    children: [
                                      Text('Discard', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                      SizedBox(width: 8),
                                      Icon(Icons.delete, color: Colors.white, size: 28),
                                    ],
                                  ),
                                ),
                                onDismissed: (direction) {
                                  if (direction == DismissDirection.startToEnd) {
                                    HapticFeedback.lightImpact();
                                    controller.approveItem(item.tempId);
                                  } else {
                                    HapticFeedback.mediumImpact();
                                    controller.discardItem(item.tempId);
                                  }
                                },
                                child: Card(
                                  margin: const EdgeInsets.symmetric(vertical: 6),
                                  elevation: isApproved ? 1 : 3,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                    side: BorderSide(
                                      color: isApproved
                                          ? Colors.green.shade400
                                          : (item.isHighConfidence ? Colors.grey.shade300 : Colors.amber.shade400),
                                      width: isApproved ? 1.5 : 1.0,
                                    ),
                                  ),
                                  child: Padding(
                                    padding: const EdgeInsets.all(12),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        // Top Row: Item index, category, confidence badge, approve checkbox
                                        Row(
                                          children: [
                                            CircleAvatar(
                                              radius: 12,
                                              backgroundColor: isApproved ? Colors.green.shade100 : Colors.grey.shade200,
                                              child: Text(
                                                '${index + 1}',
                                                style: TextStyle(
                                                  fontSize: 11,
                                                  fontWeight: FontWeight.bold,
                                                  color: isApproved ? Colors.green.shade800 : Colors.black87,
                                                ),
                                              ),
                                            ),
                                            const SizedBox(width: 8),
                                            Chip(
                                              label: Text(item.parsed.category, style: const TextStyle(fontSize: 11)),
                                              visualDensity: VisualDensity.compact,
                                              padding: EdgeInsets.zero,
                                            ),
                                            const Spacer(),
                                            _buildConfidenceBadge(item.parsed.confidence),
                                            const SizedBox(width: 8),
                                            IconButton(
                                              icon: Icon(
                                                isApproved ? Icons.check_circle : Icons.radio_button_unchecked,
                                                color: isApproved ? Colors.green : Colors.grey,
                                              ),
                                              onPressed: () {
                                                if (isApproved) {
                                                  controller.unapproveItem(item.tempId);
                                                } else {
                                                  controller.approveItem(item.tempId);
                                                }
                                              },
                                            ),
                                          ],
                                        ),

                                        // Optional Cropped Snippet Preview
                                        if (item.snippetBytes != null) ...[
                                          const SizedBox(height: 8),
                                          Container(
                                            height: 54,
                                            width: double.infinity,
                                            decoration: BoxDecoration(
                                              color: Colors.black87,
                                              borderRadius: BorderRadius.circular(6),
                                              border: Border.all(color: Colors.grey.shade600),
                                            ),
                                            child: ClipRRect(
                                              borderRadius: BorderRadius.circular(6),
                                              child: Image.memory(
                                                item.snippetBytes!,
                                                fit: BoxFit.contain,
                                              ),
                                            ),
                                          ),
                                        ],

                                        const SizedBox(height: 8),
                                        // Item Name and Inline Editor
                                        Text(
                                          item.parsed.item,
                                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                        ),
                                        const SizedBox(height: 4),

                                        // Pricing & Quantity Line
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            Text(
                                              '${item.parsed.quantity} ${item.parsed.unit} × \$${item.parsed.unitPrice.toStringAsFixed(2)}',
                                              style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
                                            ),
                                            Text(
                                              '\$${item.parsed.totalPrice.toStringAsFixed(2)}',
                                              style: TextStyle(
                                                fontSize: 17,
                                                fontWeight: FontWeight.bold,
                                                color: Theme.of(context).colorScheme.primary,
                                              ),
                                            ),
                                          ],
                                        ),

                                        const SizedBox(height: 8),
                                        // Tiers and ratings chips
                                        Wrap(
                                          spacing: 6,
                                          children: [
                                            _buildTierChip('Store', item.parsed.storeTier, item.parsed.storeRating),
                                            _buildTierChip('Brand', item.parsed.brandTier, item.parsed.brandRating),
                                            _buildTierChip('Prod', item.parsed.productTier, item.parsed.productRating),
                                          ],
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),

              // Sticky Floating Bottom Balance HUD
              Align(
                alignment: Alignment.bottomCenter,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.15),
                        blurRadius: 10,
                        offset: const Offset(0, -3),
                      ),
                    ],
                    border: Border(
                      top: BorderSide(
                        color: isBalanced ? Colors.green.shade500 : Colors.amber.shade700,
                        width: 2.0,
                      ),
                    ),
                  ),
                  child: SafeArea(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Audited: \$${controller.calculatedTotal.toStringAsFixed(2)} / Target: \$${controller.detectedTotal.toStringAsFixed(2)}',
                                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                                ),
                                Row(
                                  children: [
                                    Icon(
                                      isBalanced ? Icons.check_circle : Icons.warning,
                                      size: 14,
                                      color: isBalanced ? Colors.green : Colors.amber.shade800,
                                    ),
                                    const SizedBox(width: 4),
                                    Text(
                                      isBalanced
                                          ? 'Balanced perfectly (Δ = \$0.00)'
                                          : 'Delta: \$${controller.balanceDelta.toStringAsFixed(2)} mismatch',
                                      style: TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                        color: isBalanced ? Colors.green : Colors.amber.shade900,
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            if (!isBalanced)
                              TextButton(
                                onPressed: () => controller.reconcileBalance(),
                                child: const Text('Auto-Balance', style: TextStyle(fontSize: 12)),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            icon: const Icon(Icons.cloud_upload),
                            label: Text(
                              'Commit to Ledger (${controller.approvedIds.length > 0 ? controller.approvedIds.length : controller.activeItems.length} items)',
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: isBalanced ? Colors.green.shade700 : null,
                              foregroundColor: isBalanced ? Colors.white : null,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                            onPressed: _commitAndFinish,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildConfidenceBadge(double conf) {
    Color bg = Colors.green.shade100;
    Color fg = Colors.green.shade800;
    if (conf < 0.70) {
      bg = Colors.red.shade100;
      fg = Colors.red.shade800;
    } else if (conf < 0.90) {
      bg = Colors.amber.shade100;
      fg = Colors.amber.shade900;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        '${(conf * 100).toInt()}% conf',
        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: fg),
      ),
    );
  }

  Widget _buildTierChip(String label, String tier, double rating) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Text(
        '$label: $tier ★${rating.toStringAsFixed(1)}',
        style: TextStyle(fontSize: 10, color: Colors.grey.shade800),
      ),
    );
  }
}

