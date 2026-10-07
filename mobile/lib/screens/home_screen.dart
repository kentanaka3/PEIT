import 'package:flutter/material.dart';

import '../controllers/receipt_review_controller.dart';
import '../data/database.dart';
import '../models/receipt_entry.dart';
import '../ocr/parser.dart';
import '../services/pairing_service.dart';
import '../services/secure_storage_service.dart';
import '../services/sync_service.dart';
import 'add_entry_screen.dart';
import 'dashboard_screen.dart';
import 'pairing_dialog.dart';
import 'receipt_card_stream_screen.dart';

/// Main Dashboard Screen displaying local statistics, sync controls, LAN connection target, and recent transactions.
class HomeScreen extends StatefulWidget {
  final AppDatabase database;
  final SyncService syncService;
  final SecureStorageService? secureStorage;
  final PairingService? pairingService;

  const HomeScreen({
    super.key,
    required this.database,
    required this.syncService,
    this.secureStorage,
    this.pairingService,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _totalEntries = 0;
  int _pendingSync = 0;
  bool _isSyncing = false;
  bool _isDiscovering = false;
  bool _isPaired = false;
  String _syncProgressText = '';
  ServerHealth? _serverHealth;
  List<ReceiptEntryModel> _recentEntries = [];

  @override
  void initState() {
    super.initState();
    _refreshData();
    _checkServer();
    _checkPairingStatus();
  }

  Future<void> _checkPairingStatus() async {
    if (widget.secureStorage != null) {
      final paired = await widget.secureStorage!.isPaired();
      if (mounted) {
        setState(() {
          _isPaired = paired;
        });
      }
    }
  }

  void _refreshData() {
    setState(() {
      _totalEntries = widget.database.getTotalCount();
      _pendingSync = widget.database.getPendingCount();
      _recentEntries = widget.database.getAllEntries(limit: 20);
    });
  }

  Future<void> _checkServer() async {
    final health = await widget.syncService.checkHealth();
    if (mounted) {
      setState(() {
        _serverHealth = health;
      });
    }
  }

  Future<void> _autoDiscoverServer() async {
    if (_isDiscovering) return;
    setState(() => _isDiscovering = true);

    try {
      final discoveredUrl = await widget.syncService.discoverServer();
      if (!mounted) return;

      if (discoveredUrl != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Discovered PEIT desktop daemon at $discoveredUrl'),
            backgroundColor: Colors.green.shade700,
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('No active PEIT daemon found on local network candidates.'),
            backgroundColor: Colors.orange.shade800,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Auto-discovery error: $e'),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isDiscovering = false);
        _checkServer();
      }
    }
  }

  Future<void> _showServerSettingsDialog() async {
    final urlController = TextEditingController(text: widget.syncService.baseUrl);

    final updated = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Desktop Sync Connection'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Enter the address of your desktop PEIT daemon ("peit --serve"):',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: urlController,
              decoration: const InputDecoration(
                labelText: 'Server URL',
                hintText: 'http://192.168.1.50:8000',
                prefixIcon: Icon(Icons.dns),
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.url,
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                ActionChip(
                  avatar: const Icon(Icons.computer, size: 16),
                  label: const Text('Localhost'),
                  onPressed: () => urlController.text = 'http://127.0.0.1:8000',
                ),
                ActionChip(
                  avatar: const Icon(Icons.android, size: 16),
                  label: const Text('Android Host'),
                  onPressed: () => urlController.text = 'http://10.0.2.2:8000',
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              widget.syncService.baseUrl = urlController.text.trim();
              Navigator.of(ctx).pop(true);
            },
            child: const Text('Save & Probe'),
          ),
        ],
      ),
    );

    if (updated == true) {
      await _checkServer();
    }
  }

  void _showPairingDialog() {
    if (widget.pairingService == null || widget.secureStorage == null) return;

    showDialog(
      context: context,
      builder: (ctx) => PairingDialog(
        pairingService: widget.pairingService!,
        secureStorage: widget.secureStorage!,
        currentServerUrl: widget.syncService.baseUrl,
        onPairingChanged: () {
          _checkPairingStatus();
        },
      ),
    );
  }

  Future<void> _syncNow() async {
    if (_isSyncing) return;
    setState(() {
      _isSyncing = true;
      _syncProgressText = 'Preparing sync batches...';
    });

    try {
      final res = await widget.syncService.pushPendingEntries(
        onProgress: (current, total) {
          if (mounted) {
            setState(() {
              _syncProgressText = 'Syncing batch $current of $total...';
            });
          }
        },
      );
      if (!mounted) return;

      if (res.isSuccess) {
        final detail = res.quarantined > 0
            ? ' (quarantined: ${res.quarantined} invalid)'
            : '';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Sync successful! Imported: ${res.imported}, Skipped: ${res.skipped}$detail'),
            backgroundColor: Colors.green.shade700,
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Sync notice: ${res.errorMessage ?? "Validation issues"} (Imported: ${res.imported})'),
            backgroundColor: Colors.orange.shade800,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Sync exception: $e'),
            backgroundColor: Colors.red.shade700,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isSyncing = false;
          _syncProgressText = '';
        });
        _refreshData();
        _checkServer();
      }
    }
  }

  void _openAddEntry() async {
    final result = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (ctx) => AddEntryScreen(database: widget.database),
      ),
    );
    if (result == true) {
      _refreshData();
    }
  }

  void _openReceiptScan() async {
    final textController = TextEditingController();
    final shouldProceed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Receipt OCR Input'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Paste raw receipt OCR text or sample receipt lines to parse and audit:',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: textController,
              maxLines: 8,
              decoration: const InputDecoration(
                hintText: 'SORIANA HIPER\n2026-10-06\nLECHE ENTERA 1L 24.50\nPAN BLANCO 48.00\nTOTAL 72.50',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Parse & Review'),
          ),
        ],
      ),
    );

    if (shouldProceed == true && textController.text.trim().isNotEmpty) {
      final parser = ReceiptParser();
      final parsedReceipt = parser.parseText(textController.text.trim());
      final reviewController = ReceiptReviewController.fromParsedReceipt(parsedReceipt);

      if (!mounted) return;
      final committed = await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (ctx) => ReceiptCardStreamScreen(
            controller: reviewController,
            database: widget.database,
          ),
        ),
      );

      if (committed == true) {
        _refreshData();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isOnline = _serverHealth?.isHealthy ?? false;

    return Scaffold(
      appBar: AppBar(
        title: const Text('PEIT Mobile'),
        actions: [
          IconButton(
            icon: const Icon(Icons.analytics_outlined),
            tooltip: 'Econometric Dashboard',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (ctx) => DashboardScreen(database: widget.database),
                ),
              );
            },
          ),
          IconButton(
            icon: Icon(
              _isPaired ? Icons.verified_user : Icons.phonelink_lock,
              color: _isPaired ? Colors.green.shade400 : null,
            ),
            tooltip: _isPaired ? 'Paired with Desktop' : 'Device Unpaired (Tap to Pair)',
            onPressed: _showPairingDialog,
          ),
          IconButton(
            icon: const Icon(Icons.settings_ethernet),
            tooltip: 'Server Settings',
            onPressed: _showServerSettingsDialog,
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh data',
            onPressed: () {
              _refreshData();
              _checkServer();
              _checkPairingStatus();
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          _refreshData();
          await _checkServer();
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Status and Sync Card
            Card(
              elevation: 3,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: isOnline ? Colors.green.shade100 : Colors.orange.shade100,
                          child: Icon(
                            isOnline ? Icons.cloud_done : Icons.cloud_off,
                            color: isOnline ? Colors.green.shade800 : Colors.orange.shade800,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                isOnline ? 'Desktop Daemon Connected' : 'Desktop Daemon Offline',
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                              ),
                              Text(
                                isOnline
                                    ? 'v${_serverHealth!.version} • ${_serverHealth!.entryCount} entries in ledger'
                                    : 'Make sure "peit --serve" is running',
                                style: TextStyle(color: Colors.grey.shade700, fontSize: 13),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    // Connection Target Bar with Auto-Discovery & Setting buttons
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.5),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.link, size: 16, color: Colors.blueGrey.shade700),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              'Target: ${widget.syncService.baseUrl}',
                              style: TextStyle(fontSize: 12, color: Colors.blueGrey.shade800, fontFamily: 'monospace'),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          IconButton(
                            icon: _isDiscovering
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.wifi_find, size: 18),
                            tooltip: 'Auto-discover desktop daemon on LAN',
                            onPressed: _isDiscovering ? null : _autoDiscoverServer,
                            visualDensity: VisualDensity.compact,
                          ),
                          IconButton(
                            icon: const Icon(Icons.edit, size: 16),
                            tooltip: 'Edit connection URL',
                            onPressed: _showServerSettingsDialog,
                            visualDensity: VisualDensity.compact,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    // Pairing Security Banner
                    InkWell(
                      onTap: _showPairingDialog,
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: _isPaired ? Colors.green.shade50 : Colors.amber.shade50,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: _isPaired ? Colors.green.shade200 : Colors.amber.shade300,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              _isPaired ? Icons.lock_outline : Icons.lock_open,
                              size: 16,
                              color: _isPaired ? Colors.green.shade800 : Colors.amber.shade900,
                            ),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                _isPaired
                                    ? 'Paired with Desktop Daemon (HMAC Secured)'
                                    : 'Device Unpaired (Tap to Enter PIN & Pair)',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: _isPaired ? Colors.green.shade900 : Colors.amber.shade900,
                                ),
                              ),
                            ),
                            Icon(
                              Icons.chevron_right,
                              size: 16,
                              color: _isPaired ? Colors.green.shade800 : Colors.amber.shade800,
                            ),
                          ],
                        ),
                      ),
                    ),
                    const Divider(height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _buildStatColumn('Total Entries', _totalEntries.toString(), Icons.receipt_long),
                        _buildStatColumn('Pending Sync', _pendingSync.toString(), Icons.sync_problem,
                            highlight: _pendingSync > 0),
                      ],
                    ),
                    const SizedBox(height: 16),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: (_isSyncing || _pendingSync == 0) ? null : _syncNow,
                        icon: _isSyncing
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.sync),
                        label: Text(_isSyncing
                            ? (_syncProgressText.isNotEmpty ? _syncProgressText : 'Syncing...')
                            : 'Sync Now ($_pendingSync pending)'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Prominent Dashboard Quick-Access Card
            Card(
              elevation: 2,
              color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.4),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: Theme.of(context).colorScheme.primary.withOpacity(0.3)),
              ),
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: Theme.of(context).colorScheme.primary,
                  foregroundColor: Theme.of(context).colorScheme.onPrimary,
                  child: const Icon(Icons.insights),
                ),
                title: const Text(
                  'Econometric Dashboard',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                subtitle: const Text(
                  'Real-time cash flow, category breakdown & personal inflation index',
                  style: TextStyle(fontSize: 12),
                ),
                trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (ctx) => DashboardScreen(database: widget.database),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 16),

            // Recent Transactions Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Recent Transactions (${_recentEntries.length})',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
                TextButton(
                  onPressed: _refreshData,
                  child: const Text('View All'),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Entries List
            if (_recentEntries.isEmpty)
              Card(
                elevation: 0,
                color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.4),
                child: const Padding(
                  padding: EdgeInsets.all(32),
                  child: Column(
                    children: [
                      Icon(Icons.inbox, size: 48, color: Colors.grey),
                      SizedBox(height: 12),
                      Text('No transaction entries yet', style: TextStyle(fontWeight: FontWeight.bold)),
                      SizedBox(height: 4),
                      Text('Tap the + button below to log your first receipt entry.', textAlign: TextAlign.center),
                    ],
                  ),
                ),
              )
            else
              ..._recentEntries.map((entry) => _buildEntryTile(entry)),
          ],
        ),
      ),
      floatingActionButton: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          FloatingActionButton.extended(
            heroTag: 'fab_scan_receipt',
            onPressed: _openReceiptScan,
            icon: const Icon(Icons.document_scanner),
            label: const Text('Scan / OCR'),
            backgroundColor: Colors.teal.shade700,
            foregroundColor: Colors.white,
          ),
          const SizedBox(width: 12),
          FloatingActionButton.extended(
            heroTag: 'fab_add_entry',
            onPressed: _openAddEntry,
            icon: const Icon(Icons.add),
            label: const Text('Add Entry'),
          ),
        ],
      ),
    );
  }

  Widget _buildStatColumn(String label, String value, IconData icon, {bool highlight = false}) {
    return Column(
      children: [
        Icon(icon, color: highlight ? Colors.amber.shade800 : Colors.blueGrey, size: 28),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: highlight ? Colors.amber.shade900 : null,
          ),
        ),
        Text(label, style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
      ],
    );
  }

  Widget _buildEntryTile(ReceiptEntryModel entry) {
    final isExpense = entry.paidTotal < 0;
    final absAmount = entry.paidTotal.abs().toStringAsFixed(2);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 1,
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: isExpense ? Colors.red.shade50 : Colors.green.shade50,
          child: Icon(
            isExpense ? Icons.arrow_downward : Icons.arrow_upward,
            color: isExpense ? Colors.red.shade700 : Colors.green.shade700,
            size: 18,
          ),
        ),
        title: Text(entry.item, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text(
          '${entry.receiptDate} • ${entry.merchant} • ${entry.category}\n'
          'Tier: ${entry.storeTier}/${entry.brandTier}/${entry.productTier} • Rating: ${entry.storeRating}★',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              '${isExpense ? "-" : "+"}${entry.currency} $absAmount',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 14,
                color: isExpense ? Colors.red.shade800 : Colors.green.shade800,
              ),
            ),
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  entry.isSynced ? Icons.cloud_done : Icons.cloud_upload_outlined,
                  size: 14,
                  color: entry.isSynced ? Colors.green : Colors.grey,
                ),
                const SizedBox(width: 4),
                Text(
                  entry.isSynced ? 'Synced' : 'Pending',
                  style: TextStyle(
                    fontSize: 11,
                    color: entry.isSynced ? Colors.green : Colors.grey.shade600,
                  ),
                ),
              ],
            ),
          ],
        ),
        isThreeLine: true,
      ),
    );
  }
}
