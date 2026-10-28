import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/database.dart';
import '../data/schema_constants.dart';
import '../models/receipt_entry.dart';

/// Form screen for manual receipt and expenditure entry.
class AddEntryScreen extends StatefulWidget {
  final AppDatabase database;

  const AddEntryScreen({super.key, required this.database});

  @override
  State<AddEntryScreen> createState() => _AddEntryScreenState();
}

class _AddEntryScreenState extends State<AddEntryScreen> {
  final _formKey = GlobalKey<FormState>();

  // Text Editing Controllers
  late TextEditingController _receiptIdController;
  late TextEditingController _dateController;
  late TextEditingController _merchantController;
  late TextEditingController _itemController;
  late TextEditingController _brandController;
  late TextEditingController _quantityController;
  late TextEditingController _packSizeController;
  late TextEditingController _unitController;
  late TextEditingController _unitPriceController;
  late TextEditingController _paidTotalController;
  late TextEditingController _notesController;

  // Form State
  String _category = 'Food and beverages';
  String _currency = 'MXN';
  String _eventType = 'recurring';
  String _storeTier = 'A';
  double _storeRating = 5.0;
  String _brandTier = 'A';
  double _brandRating = 5.0;
  String _productTier = 'A';
  double _productRating = 5.0;
  String _availability = 'in_stock';
  String _account = 'default:checking';

  final List<String> _categories = [
    'Food and beverages',
    'Housing, water, electricity, gas and other fuels',
    'Furnishings, household equipment and routine maintenance',
    'Health',
    'Transport',
    'Communication',
    'Recreation and culture',
    'Education',
    'Restaurants and hotels',
    'Miscellaneous goods and services',
    'General',
  ];

  final List<String> _tiers = ['A', 'B', 'C', 'D', 'E'];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    final dateStr = DateFormat('yyyy-MM-dd').format(now);
    final autoReceiptId = 'rec-${DateFormat('yyyyMMdd-HHmmss').format(now)}';

    _receiptIdController = TextEditingController(text: autoReceiptId);
    _dateController = TextEditingController(text: dateStr);
    _merchantController = TextEditingController();
    _itemController = TextEditingController();
    _brandController = TextEditingController();
    _quantityController = TextEditingController(text: '1.0');
    _packSizeController = TextEditingController(text: '1.0');
    _unitController = TextEditingController(text: 'unit');
    _unitPriceController = TextEditingController();
    _paidTotalController = TextEditingController();
    _notesController = TextEditingController();

    // Auto calculate unit price when paid total or quantity changes
    _paidTotalController.addListener(_recalcUnitPrice);
    _quantityController.addListener(_recalcUnitPrice);
  }

  void _recalcUnitPrice() {
    final paid = double.tryParse(_paidTotalController.text);
    final qty = double.tryParse(_quantityController.text);
    if (paid != null && qty != null && qty > 0) {
      final unitPrice = (paid.abs() / qty);
      _unitPriceController.text = unitPrice.toStringAsFixed(2);
    }
  }

  @override
  void dispose() {
    _paidTotalController.removeListener(_recalcUnitPrice);
    _quantityController.removeListener(_recalcUnitPrice);
    _receiptIdController.dispose();
    _dateController.dispose();
    _merchantController.dispose();
    _itemController.dispose();
    _brandController.dispose();
    _quantityController.dispose();
    _packSizeController.dispose();
    _unitController.dispose();
    _unitPriceController.dispose();
    _paidTotalController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final current = DateTime.tryParse(_dateController.text) ?? DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (picked != null) {
      setState(() {
        _dateController.text = DateFormat('yyyy-MM-dd').format(picked);
      });
    }
  }

  void _saveEntry() {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final qty = double.parse(_quantityController.text.trim());
    final packSize = double.tryParse(_packSizeController.text.trim()) ?? 1.0;
    var paidTotal = double.parse(_paidTotalController.text.trim());
    final unitPrice = double.tryParse(_unitPriceController.text.trim()) ?? (paidTotal.abs() / qty);

    // Apply PEIT convention: expenditure events (recurring, one_off) are negative paid_total
    if ((_eventType == 'recurring' || _eventType == 'one_off') && paidTotal > 0) {
      paidTotal = -paidTotal;
    } else if ((_eventType == 'income' || _eventType == 'refund') && paidTotal < 0) {
      paidTotal = paidTotal.abs();
    }

    final entry = ReceiptEntryModel.create(
      receiptId: _receiptIdController.text.trim(),
      receiptDate: _dateController.text.trim(),
      merchant: _merchantController.text.trim(),
      item: _itemController.text.trim(),
      brand: _brandController.text.trim(),
      category: _category,
      quantity: qty,
      packSize: packSize,
      unit: _unitController.text.trim(),
      unitPrice: unitPrice,
      currency: _currency.trim().toUpperCase(),
      paidTotal: paidTotal,
      eventType: _eventType,
      storeTier: _storeTier,
      storeRating: _storeRating,
      brandTier: _brandTier,
      brandRating: _brandRating,
      productTier: _productTier,
      productRating: _productRating,
      availability: _availability,
      notes: _notesController.text.trim(),
      account: _account.trim(),
      isSynced: false,
    );

    widget.database.insertEntry(entry);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Added entry for ${entry.item} (${entry.currency} ${entry.paidTotal.abs().toStringAsFixed(2)})'),
        backgroundColor: Colors.green.shade700,
      ),
    );

    Navigator.of(context).pop(true);
  }

  Widget _buildTierSelector({
    required String label,
    required String currentTier,
    required ValueChanged<String> onChanged,
  }) {
    return Row(
      children: [
        SizedBox(width: 80, child: Text(label, style: const TextStyle(fontWeight: FontWeight.bold))),
        Expanded(
          child: SegmentedButton<String>(
            segments: _tiers.map((t) => ButtonSegment(value: t, label: Text(t))).toList(),
            selected: {currentTier},
            onSelectionChanged: (set) => onChanged(set.first),
          ),
        ),
      ],
    );
  }

  Widget _buildRatingSlider({
    required String label,
    required double currentRating,
    required ValueChanged<double> onChanged,
  }) {
    return Row(
      children: [
        SizedBox(width: 80, child: Text('$label (${currentRating.toStringAsFixed(1)}★)')),
        Expanded(
          child: Slider(
            value: currentRating,
            min: 1.0,
            max: 5.0,
            divisions: 8, // 0.5 steps
            label: currentRating.toStringAsFixed(1),
            onChanged: onChanged,
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Add Expenditure Item'),
        actions: [
          IconButton(
            icon: const Icon(Icons.check),
            tooltip: 'Save Entry',
            onPressed: _saveEntry,
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Transaction Essentials Card
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Receipt Information', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _receiptIdController,
                            decoration: const InputDecoration(labelText: 'Receipt ID *', prefixIcon: Icon(Icons.receipt)),
                            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _dateController,
                            readOnly: true,
                            onTap: _pickDate,
                            decoration: const InputDecoration(
                              labelText: 'Date (YYYY-MM-DD) *',
                              prefixIcon: Icon(Icons.calendar_today),
                            ),
                            validator: (v) => (v == null || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(v)) ? 'Invalid date' : null,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _merchantController,
                      decoration: const InputDecoration(labelText: 'Store / Merchant *', prefixIcon: Icon(Icons.store)),
                      validator: (v) => (v == null || v.trim().isEmpty) ? 'Merchant is required' : null,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Item Details Card
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Item & Pricing', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _itemController,
                      decoration: const InputDecoration(labelText: 'Item Name *', prefixIcon: Icon(Icons.shopping_bag)),
                      validator: (v) => (v == null || v.trim().isEmpty) ? 'Item name required' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _brandController,
                      decoration: const InputDecoration(labelText: 'Brand (Optional)', prefixIcon: Icon(Icons.branding_watermark)),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: _category,
                      decoration: const InputDecoration(labelText: 'Category *', prefixIcon: Icon(Icons.category)),
                      items: _categories.map((c) => DropdownMenuItem(value: c, child: Text(c, overflow: TextOverflow.ellipsis))).toList(),
                      onChanged: (v) => setState(() => _category = v!),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _quantityController,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Quantity *'),
                            validator: (v) {
                              final numVal = double.tryParse(v ?? '');
                              if (numVal == null || numVal <= 0) return 'Must be > 0';
                              return null;
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: _unitController,
                            decoration: const InputDecoration(labelText: 'Unit *'),
                            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: _packSizeController,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Pack Size'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _paidTotalController,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                            decoration: const InputDecoration(labelText: 'Total Price / Paid *', prefixIcon: Icon(Icons.attach_money)),
                            validator: (v) {
                              if (v == null || double.tryParse(v) == null) return 'Numeric required';
                              return null;
                            },
                          ),
                        ),
                        const SizedBox(width: 12),
                        SizedBox(
                          width: 90,
                          child: TextFormField(
                            initialValue: _currency,
                            maxLength: 3,
                            decoration: const InputDecoration(labelText: 'Curr *', counterText: ''),
                            onChanged: (v) => _currency = v,
                            validator: (v) => (v == null || v.length != 3) ? '3-letter' : null,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _unitPriceController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'Calculated Unit Price', prefixIcon: Icon(Icons.calculate_outlined)),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Classification & Evaluation Card
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Tier & Quality Rating', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 12),
                    _buildTierSelector(
                      label: 'Store',
                      currentTier: _storeTier,
                      onChanged: (t) => setState(() => _storeTier = t),
                    ),
                    _buildRatingSlider(
                      label: 'Store',
                      currentRating: _storeRating,
                      onChanged: (r) => setState(() => _storeRating = r),
                    ),
                    const Divider(),
                    _buildTierSelector(
                      label: 'Brand',
                      currentTier: _brandTier,
                      onChanged: (t) => setState(() => _brandTier = t),
                    ),
                    _buildRatingSlider(
                      label: 'Brand',
                      currentRating: _brandRating,
                      onChanged: (r) => setState(() => _brandRating = r),
                    ),
                    const Divider(),
                    _buildTierSelector(
                      label: 'Product',
                      currentTier: _productTier,
                      onChanged: (t) => setState(() => _productTier = t),
                    ),
                    _buildRatingSlider(
                      label: 'Product',
                      currentRating: _productRating,
                      onChanged: (r) => setState(() => _productRating = r),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Availability & Event Type Card
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Market Status & Metadata', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 12),
                    const Text('Availability:'),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 8,
                      children: PeitSchemaConstants.availabilityStatuses.map((status) {
                        return ChoiceChip(
                          label: Text(status.replaceAll('_', ' ')),
                          selected: _availability == status,
                          onSelected: (selected) {
                            if (selected) setState(() => _availability = status);
                          },
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: _eventType,
                      decoration: const InputDecoration(labelText: 'Event Type *'),
                      items: PeitSchemaConstants.eventTypes
                          .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                          .toList(),
                      onChanged: (v) => setState(() => _eventType = v!),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _notesController,
                      decoration: const InputDecoration(labelText: 'Notes', prefixIcon: Icon(Icons.note)),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            ElevatedButton.icon(
              onPressed: _saveEntry,
              icon: const Icon(Icons.save),
              label: const Text('Save Transaction Item', style: TextStyle(fontSize: 16)),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }
}
