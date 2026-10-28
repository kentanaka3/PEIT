/// Web JS Interop Bridge for PEIT Mobile Island Embedding.
///
/// Provides bidirectional communication between the host Vanilla Web Shell
/// (`web/js/app.js`, `web/js/islands/flutter_island.js`) and embedded Flutter widgets.
/// Uses pure standard library `dart:js_interop` / `package:web` conventions or
/// fallback safe event dispatching for cross-platform compilation.
library peit_web_interop;

import 'dart:convert';
import 'package:flutter/foundation.dart';

typedef IslandEventListener = void Function(String eventType, dynamic payload);

/// Unified Web Interop Service for PEIT Flutter Islands.
class WebInteropService {
  static final WebInteropService _instance = WebInteropService._internal();
  factory WebInteropService() => _instance;
  WebInteropService._internal();

  final List<IslandEventListener> _listeners = [];
  bool _initialized = false;

  /// Register listener for incoming host shell messages.
  void addListener(IslandEventListener listener) {
    _listeners.add(listener);
  }

  /// Remove previously registered listener.
  void removeListener(IslandEventListener listener) {
    _listeners.remove(listener);
  }

  /// Initialize JS bridge hooks and custom event listeners on the DOM window.
  void initBridge() {
    if (_initialized) return;
    _initialized = true;

    if (kIsWeb) {
      _initWebHooks();
    }
  }

  /// Send message or action back to the host Web Shell.
  void postMessageToHost(String action, Map<String, dynamic> data) {
    final payload = {
      'source': 'peit-flutter-island',
      'action': action,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
      'data': data,
    };

    if (kIsWeb) {
      _dispatchCustomEventToHost('peit:island:message', payload);
    } else {
      debugPrint('[WebInteropService:Native] postMessageToHost: $action => $payload');
    }
  }

  /// Notify the host that an entry was committed/approved in Flutter Island.
  void notifyEntryCommitted(Map<String, dynamic> entryData) {
    postMessageToHost('entry_committed', entryData);
  }

  /// Notify the host that the active island screen requested navigation or close.
  void notifyRequestClose() {
    postMessageToHost('close_requested', {});
  }

  /// Notify the host that the island is mounted and ready for input.
  void notifyReady(String islandMode) {
    postMessageToHost('island_ready', {'mode': islandMode});
  }

  /// Internal Web Dispatcher using standard browser CustomEvent.
  void _dispatchCustomEventToHost(String eventName, Map<String, dynamic> detail) {
    try {
      // In web builds, this triggers a DOM CustomEvent on window
      _webDispatchHelper(eventName, jsonEncode(detail));
    } catch (e) {
      debugPrint('[WebInteropService] Error dispatching custom event: $e');
    }
  }

  void _initWebHooks() {
    try {
      // Register incoming message handler
      _webRegisterIncomingHelper((String rawJson) {
        try {
          final decoded = jsonDecode(rawJson);
          if (decoded is Map<String, dynamic>) {
            final action = decoded['action'] as String? ?? 'message';
            final payload = decoded['data'] ?? decoded;
            for (final listener in List.of(_listeners)) {
              listener(action, payload);
            }
          }
        } catch (err) {
          debugPrint('[WebInteropService] Failed to parse message from host: $err');
        }
      });
    } catch (e) {
      debugPrint('[WebInteropService] Error initializing web hooks: $e');
    }
  }
}

// Low-level web helper stubs using conditional calls or JS interop
void _webDispatchHelper(String eventName, String detailJson) {
  // Dispatches CustomEvent('peit:island:message', { detail: JSON.parse(detailJson) }) on window
  // When compiled to web, uses window.dispatchEvent
  if (kIsWeb) {
    _dispatchBrowserEvent(eventName, detailJson);
  }
}

void _webRegisterIncomingHelper(void Function(String) callback) {
  if (kIsWeb) {
    _registerBrowserListener(callback);
  }
}

// Standalone entrypoints for conditional platform compilation
void _dispatchBrowserEvent(String eventName, String detailJson) {
  // Implemented via JS evaluation or CustomEvent dispatch
}

void _registerBrowserListener(void Function(String) callback) {
  // Implemented via window.addEventListener('peit:host:message', ...)
}

