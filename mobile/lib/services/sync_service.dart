import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

import '../data/database.dart';
import '../models/receipt_entry.dart';

/// Health status response model from desktop daemon GET /api/v1/health
class ServerHealth {
  final bool isHealthy;
  final String version;
  final int entryCount;
  final int schemaColumns;
  final String? ledgerPath;
  final String? errorMessage;

  const ServerHealth({
    required this.isHealthy,
    this.version = '',
    this.entryCount = 0,
    this.schemaColumns = 0,
    this.ledgerPath,
    this.errorMessage,
  });

  factory ServerHealth.fromJson(Map<String, dynamic> json) {
    return ServerHealth(
      isHealthy: json['status'] == 'ok',
      version: (json['version'] as String?) ?? '',
      entryCount: (json['entry_count'] as num?)?.toInt() ?? 0,
      schemaColumns: (json['schema_columns'] as num?)?.toInt() ?? 0,
      ledgerPath: json['ledger'] as String?,
    );
  }

  factory ServerHealth.error(String message) {
    return ServerHealth(
      isHealthy: false,
      errorMessage: message,
    );
  }
}

/// Result of a synchronization push operation
class SyncPushResult {
  final bool isSuccess;
  final int imported;
  final int skipped;
  final int quarantined;
  final int totalBatches;
  final List<String> entryIds;
  final String? errorMessage;
  final List<Map<String, dynamic>>? validationIssues;

  const SyncPushResult({
    required this.isSuccess,
    this.imported = 0,
    this.skipped = 0,
    this.quarantined = 0,
    this.totalBatches = 0,
    this.entryIds = const [],
    this.errorMessage,
    this.validationIssues,
  });

  factory SyncPushResult.success({
    required int imported,
    required int skipped,
    required List<String> entryIds,
    int quarantined = 0,
    int totalBatches = 1,
  }) {
    return SyncPushResult(
      isSuccess: true,
      imported: imported,
      skipped: skipped,
      quarantined: quarantined,
      totalBatches: totalBatches,
      entryIds: entryIds,
    );
  }

  factory SyncPushResult.error(
    String message, {
    int imported = 0,
    int skipped = 0,
    int quarantined = 0,
    int totalBatches = 0,
    List<String> entryIds = const [],
    List<Map<String, dynamic>>? issues,
  }) {
    return SyncPushResult(
      isSuccess: false,
      imported: imported,
      skipped: skipped,
      quarantined: quarantined,
      totalBatches: totalBatches,
      entryIds: entryIds,
      errorMessage: message,
      validationIssues: issues,
    );
  }
}

/// HTTP Sync Client communicating with PEIT desktop daemon (src/peit/server.py).
class SyncService {
  String baseUrl;
  final http.Client _client;
  final AppDatabase database;

  /// Default batch size for chunking pushes to avoid DoS / payload ceilings.
  static const int defaultBatchSize = 100;

  SyncService({
    required this.baseUrl,
    required this.database,
    http.Client? client,
  }) : _client = client ?? http.Client();

  /// Normalized URI generator
  Uri _uri(String path, [String? overrideBaseUrl]) {
    final target = overrideBaseUrl ?? baseUrl;
    final cleanBase = target.endsWith('/') ? target.substring(0, target.length - 1) : target;
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$cleanBase$cleanPath');
  }

  /// Platform-aware candidates for auto-discovery
  static List<String> getDiscoveryCandidates({int port = 8000, List<String>? customHosts}) {
    final candidates = <String>[];

    // Priority 1: User or custom hosts if specified
    if (customHosts != null) {
      for (final host in customHosts) {
        final trimmed = host.trim();
        if (trimmed.isNotEmpty) {
          final formatted = trimmed.startsWith('http://') || trimmed.startsWith('https://')
              ? trimmed
              : 'http://$trimmed:$port';
          if (!candidates.contains(formatted)) candidates.add(formatted);
        }
      }
    }

    // Platform-specific defaults
    try {
      if (Platform.isAndroid) {
        candidates.add('http://10.0.2.2:$port'); // Android official emulator host loopback
      } else if (Platform.isIOS || Platform.isMacOS) {
        candidates.add('http://127.0.0.1:$port'); // iOS simulator / macOS localhost
      }
    } catch (_) {
      // Platform check may throw in pure unit test environments; add both defaults
      candidates.add('http://127.0.0.1:$port');
      candidates.add('http://10.0.2.2:$port');
    }

    // Fallbacks
    if (!candidates.contains('http://127.0.0.1:$port')) {
      candidates.add('http://127.0.0.1:$port');
    }
    if (!candidates.contains('http://localhost:$port')) {
      candidates.add('http://localhost:$port');
    }

    return candidates;
  }

  /// Probe a specific candidate URL via GET /api/v1/health.
  /// Returns ServerHealth if valid and healthy, otherwise null.
  Future<ServerHealth?> probeCandidate(
    String candidateUrl, {
    Duration timeout = const Duration(milliseconds: 1500),
  }) async {
    try {
      final probeUri = _uri('/api/v1/health', candidateUrl);
      final response = await _client
          .get(probeUri, headers: {'Accept': 'application/json'})
          .timeout(timeout);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body) as Map<String, dynamic>;
        final health = ServerHealth.fromJson(data);
        // Schema check: must report schema_columns == 25
        if (health.isHealthy && health.schemaColumns == 25) {
          return health;
        }
      }
    } catch (_) {
      // Offline or timed out
    }
    return null;
  }

  /// Automatically discover active PEIT server on local candidates.
  /// If an active server with schema 25 is found, update [baseUrl] and return the URL.
  Future<String?> discoverServer({
    int port = 8000,
    List<String>? customHosts,
    Duration candidateTimeout = const Duration(milliseconds: 1500),
  }) async {
    final candidates = getDiscoveryCandidates(port: port, customHosts: customHosts);
    for (final candidate in candidates) {
      final health = await probeCandidate(candidate, timeout: candidateTimeout);
      if (health != null && health.isHealthy) {
        baseUrl = candidate;
        return candidate;
      }
    }
    return null;
  }

  /// Check connectivity and health of desktop daemon via GET /api/v1/health.
  Future<ServerHealth> checkHealth({Duration timeout = const Duration(seconds: 5)}) async {
    try {
      final response = await _client
          .get(_uri('/api/v1/health'), headers: {'Accept': 'application/json'})
          .timeout(timeout);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body) as Map<String, dynamic>;
        return ServerHealth.fromJson(data);
      } else {
        return ServerHealth.error('Server returned HTTP status ${response.statusCode}');
      }
    } catch (e) {
      return ServerHealth.error('Failed to connect to daemon: $e');
    }
  }

  /// Push a single batch of entries to /api/v1/sync/push.
  Future<Map<String, dynamic>> _sendBatch({
    required List<ReceiptEntryModel> batch,
    required bool force,
    required String account,
    required Duration timeout,
  }) async {
    final payload = {
      'entries': batch.map((e) => e.toSyncJson()).toList(),
      'force': force,
      'account': account,
    };

    final response = await _client
        .post(
          _uri('/api/v1/sync/push'),
          headers: {
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
          },
          body: json.encode(payload),
        )
        .timeout(timeout);

    return {
      'statusCode': response.statusCode,
      'body': response.body,
    };
  }

  /// Push all pending (is_synced == 0) receipt entries to the desktop daemon.
  ///
  /// Enhancements in Phase 3:
  /// - Enforces [batchSize] chunking (default 100 entries per HTTP POST).
  /// - Progress callback [onProgress] reporting (currentBatch, totalBatches).
  /// - Robust error recovery: isolates individual failing entries when a batch fails (HTTP 400),
  ///   quarantining the invalid entry so healthy entries continue syncing.
  /// - Updates local SQLite `is_synced = 1` immediately after each successful chunk.
  Future<SyncPushResult> pushPendingEntries({
    bool force = false,
    String account = 'default:checking',
    int batchSize = defaultBatchSize,
    Duration timeout = const Duration(seconds: 15),
    void Function(int currentBatch, int totalBatches)? onProgress,
  }) async {
    final pendingEntries = database.getPendingSyncEntries();
    if (pendingEntries.isEmpty) {
      return SyncPushResult.success(imported: 0, skipped: 0, entryIds: [], totalBatches: 0);
    }

    // Split pending entries into chunks of batchSize
    final chunks = <List<ReceiptEntryModel>>[];
    for (var i = 0; i < pendingEntries.length; i += batchSize) {
      final end = (i + batchSize < pendingEntries.length) ? i + batchSize : pendingEntries.length;
      chunks.add(pendingEntries.sublist(i, end));
    }

    var totalImported = 0;
    var totalSkipped = 0;
    var totalQuarantined = 0;
    final allEntryIds = <String>[];
    final totalBatches = chunks.length;

    for (var b = 0; b < totalBatches; b++) {
      final chunk = chunks[b];
      onProgress?.call(b + 1, totalBatches);

      try {
        final res = await _sendBatch(
          batch: chunk,
          force: force,
          account: account,
          timeout: timeout,
        );

        final statusCode = res['statusCode'] as int;
        final responseBody = res['body'] as String;

        if (statusCode == 200) {
          final Map<String, dynamic> data = json.decode(responseBody) as Map<String, dynamic>;
          final imported = (data['imported'] as num?)?.toInt() ?? 0;
          final skipped = (data['skipped'] as num?)?.toInt() ?? 0;
          final entryIdsRaw = data['entry_ids'] as List<dynamic>? ?? [];
          final entryIds = entryIdsRaw.map((e) => e.toString()).toList();

          totalImported += imported;
          totalSkipped += skipped;
          allEntryIds.addAll(entryIds);

          // Mark chunk entries as synced in local SQLite
          final syncedIds = chunk.map((e) => e.entryId).toList();
          database.markEntriesSynced(syncedIds);
        } else if (statusCode == 400 || statusCode == 413) {
          // If a batch fails due to validation (400) or size (413), try single-entry fallback
          // to isolate the bad item and sync the valid items in this chunk
          if (chunk.length > 1) {
            for (final singleEntry in chunk) {
              try {
                final singleRes = await _sendBatch(
                  batch: [singleEntry],
                  force: force,
                  account: account,
                  timeout: timeout,
                );
                final singleCode = singleRes['statusCode'] as int;
                if (singleCode == 200) {
                  final Map<String, dynamic> sData = json.decode(singleRes['body'] as String) as Map<String, dynamic>;
                  totalImported += (sData['imported'] as num?)?.toInt() ?? 0;
                  totalSkipped += (sData['skipped'] as num?)?.toInt() ?? 0;
                  allEntryIds.add(singleEntry.entryId);
                  database.markEntriesSynced([singleEntry.entryId]);
                } else {
                  totalQuarantined++;
                }
              } catch (_) {
                totalQuarantined++;
              }
            }
          } else {
            // Single entry itself failed
            totalQuarantined++;
            final Map<String, dynamic> data = (statusCode == 400)
                ? (json.decode(responseBody) as Map<String, dynamic>)
                : {};
            final issues = (data['issues'] as List<dynamic>?)
                ?.map((i) => Map<String, dynamic>.from(i as Map))
                .toList();

            return SyncPushResult.error(
              data['message']?.toString() ?? 'Batch $b failed with status $statusCode',
              imported: totalImported,
              skipped: totalSkipped,
              quarantined: totalQuarantined,
              totalBatches: totalBatches,
              entryIds: allEntryIds,
              issues: issues,
            );
          }
        } else {
          return SyncPushResult.error(
            'Desktop daemon returned HTTP $statusCode: $responseBody',
            imported: totalImported,
            skipped: totalSkipped,
            quarantined: totalQuarantined,
            totalBatches: totalBatches,
            entryIds: allEntryIds,
          );
        }
      } catch (e) {
        return SyncPushResult.error(
          'Network error during sync push on batch ${b + 1} of $totalBatches: $e',
          imported: totalImported,
          skipped: totalSkipped,
          quarantined: totalQuarantined,
          totalBatches: totalBatches,
          entryIds: allEntryIds,
        );
      }
    }

    return SyncPushResult.success(
      imported: totalImported,
      skipped: totalSkipped,
      quarantined: totalQuarantined,
      totalBatches: totalBatches,
      entryIds: allEntryIds,
    );
  }

  /// Close underlying HTTP client
  void close() {
    _client.close();
  }
}
