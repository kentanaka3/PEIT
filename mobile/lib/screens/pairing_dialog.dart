import 'package:flutter/material.dart';

import '../services/pairing_service.dart';
import '../services/secure_storage_service.dart';

/// Pairing modal dialog enabling LAN pairing with PEIT desktop daemon.
class PairingDialog extends StatefulWidget {
  final PairingService pairingService;
  final SecureStorageService secureStorage;
  final String currentServerUrl;
  final VoidCallback? onPairingChanged;

  const PairingDialog({
    super.key,
    required this.pairingService,
    required this.secureStorage,
    required this.currentServerUrl,
    this.onPairingChanged,
  });

  @override
  State<PairingDialog> createState() => _PairingDialogState();
}

class _PairingDialogState extends State<PairingDialog> {
  final _pinController = TextEditingController();
  final _uriController = TextEditingController();
  final _nameController = TextEditingController(text: 'PEIT Mobile');

  bool _isPaired = false;
  bool _isLoading = false;
  String? _deviceId;
  String? _statusMessage;
  bool _isManualMode = false;

  @override
  void initState() {
    super.initState();
    _loadCurrentStatus();
  }

  Future<void> _loadCurrentStatus() async {
    final paired = await widget.secureStorage.isPaired();
    final devId = await widget.secureStorage.getOrCreateDeviceId();
    final devName = await widget.secureStorage.getDeviceName();
    if (devName != null && devName.isNotEmpty) {
      _nameController.text = devName;
    }

    if (mounted) {
      setState(() {
        _isPaired = paired;
        _deviceId = devId;
      });
    }
  }

  Future<void> _handleUnpair() async {
    setState(() => _isLoading = true);
    await widget.secureStorage.clearPairingData();
    if (mounted) {
      setState(() {
        _isPaired = false;
        _isLoading = false;
        _statusMessage = 'Device successfully unpaired.';
      });
      widget.onPairingChanged?.call();
    }
  }

  Future<void> _handleConfirmPairing() async {
    final pin = _pinController.text.trim();
    if (pin.length != 6 || !RegExp(r'^\d{6}$').hasMatch(pin)) {
      setState(() => _statusMessage = 'PIN must be exactly 6 digits.');
      return;
    }

    setState(() {
      _isLoading = true;
      _statusMessage = null;
    });

    try {
      if (_isManualMode) {
        // Parse from URI input
        final uriText = _uriController.text.trim();
        if (uriText.isEmpty) {
          setState(() => _statusMessage = 'Please enter a pairing URI or QR payload.');
          return;
        }
        final params = PairingUriParams.parse(uriText);
        await widget.pairingService.confirmPairingFromUri(
          uriParams: params,
          pin: pin,
          deviceName: _nameController.text.trim(),
        );
      } else {
        // Derive host and port from currentServerUrl
        final parsedUri = Uri.parse(widget.currentServerUrl);
        final host = parsedUri.host.isEmpty ? '127.0.0.1' : parsedUri.host;
        final port = parsedUri.port == 0 ? 8000 : parsedUri.port;

        // If user entered URI in URI box, parse that; else ask for URI
        if (_uriController.text.trim().isNotEmpty) {
          final params = PairingUriParams.parse(_uriController.text.trim());
          await widget.pairingService.confirmPairingFromUri(
            uriParams: params,
            pin: pin,
            deviceName: _nameController.text.trim(),
          );
        } else {
          // If no URI was scanned/entered, we need session_id and salt
          setState(() {
            _statusMessage = 'Please paste the pairing URI from desktop daemon ("peit --pair")';
            _isManualMode = true;
          });
          return;
        }
      }

      if (mounted) {
        setState(() {
          _isPaired = true;
          _statusMessage = 'Successfully paired with desktop server!';
        });
        widget.onPairingChanged?.call();
      }
    } on InvalidPinException {
      setState(() => _statusMessage = 'Incorrect PIN. Please re-enter the 6-digit PIN.');
    } on PairingExpiredException {
      setState(() => _statusMessage = 'Pairing session expired. Run "peit --pair" again.');
    } on PairingLockoutException {
      setState(() => _statusMessage = 'Too many failed attempts. Pairing session locked out.');
    } catch (e) {
      setState(() => _statusMessage = 'Pairing error: $e');
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Row(
        children: [
          Icon(
            _isPaired ? Icons.verified_user : Icons.phonelink_lock,
            color: _isPaired ? Colors.green.shade700 : Colors.indigo.shade700,
          ),
          const SizedBox(width: 8),
          const Text('LAN Device Pairing'),
        ],
      ),
      content: SingleChildScrollView(
        child: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Device status banner
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: _isPaired ? Colors.green.shade50 : Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: _isPaired ? Colors.green.shade300 : Colors.grey.shade300,
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      _isPaired ? Icons.check_circle : Icons.info_outline,
                      color: _isPaired ? Colors.green.shade800 : Colors.grey.shade700,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _isPaired ? 'Device is Paired' : 'Device is Unpaired',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: _isPaired ? Colors.green.shade900 : Colors.grey.shade900,
                            ),
                          ),
                          if (_deviceId != null)
                            Text(
                              'Device ID: ${_deviceId!.substring(0, 8)}...',
                              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              if (_statusMessage != null) ...[
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.blue.shade50,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    _statusMessage!,
                    style: TextStyle(fontSize: 12, color: Colors.blue.shade900),
                  ),
                ),
                const SizedBox(height: 12),
              ],

              if (!_isPaired) ...[
                const Text(
                  '1. On your desktop, run:\n   peit --pair\n2. Paste the pairing URI below and enter the 6-digit PIN displayed on your terminal.',
                  style: TextStyle(fontSize: 12, height: 1.4),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _uriController,
                  decoration: const InputDecoration(
                    labelText: 'Pairing URI / QR Payload',
                    hintText: 'peit://pair?host=192.168.1.5&port=8000&session=...&salt=...',
                    prefixIcon: Icon(Icons.qr_code),
                    border: OutlineInputBorder(),
                  ),
                  style: const TextStyle(fontSize: 12),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _pinController,
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                  decoration: const InputDecoration(
                    labelText: '6-digit PIN',
                    hintText: '123456',
                    prefixIcon: Icon(Icons.lock_clock),
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    labelText: 'Device Name (Optional)',
                    hintText: 'My Phone',
                    prefixIcon: Icon(Icons.phone_android),
                    border: OutlineInputBorder(),
                  ),
                ),
              ] else ...[
                const Text(
                  'This device is paired with the desktop daemon. All push synchronizations are cryptographically authenticated via HMAC and Bearer credentials.',
                  style: TextStyle(fontSize: 13, height: 1.4),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        if (_isPaired) ...[
          TextButton(
            onPressed: _isLoading ? null : _handleUnpair,
            style: TextButton.styleFrom(foregroundColor: Colors.red.shade700),
            child: _isLoading ? const CircularProgressIndicator() : const Text('Unpair / Disconnect'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ] else ...[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: _isLoading ? null : _handleConfirmPairing,
            child: _isLoading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Confirm PIN'),
          ),
        ],
      ],
    );
  }
}
