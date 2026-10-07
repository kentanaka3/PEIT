import 'dart:async';
import 'dart:io';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqlite3/sqlite3.dart';

import '../models/receipt_entry.dart';
import 'schema.dart';

/// AppDatabase providing robust, fast SQLite persistence for PEIT Mobile.
///
/// Implemented using direct SQLite bindings (compatible with drift/sqlite3 packages)
/// ensuring full functionality both with and without pre-compiled code generation.
class AppDatabase {
  final Database _db;

  AppDatabase(this._db) {
    _createTables();
  }

  /// Open or create database in the standard application documents directory.
  static Future<AppDatabase> openDefault() async {
    final dir = await getApplicationDocumentsDirectory();
    final dbPath = p.join(dir.path, 'peit_mobile.db');
    final db = sqlite3.open(dbPath);
    return AppDatabase(db);
  }

  /// Open an in-memory database, ideal for fast unit and integration tests.
  static AppDatabase openInMemory() {
    final db = sqlite3.openInMemory();
    return AppDatabase(db);
  }

  /// Initialize tables and indexes mirroring PEIT's 25-column specification + sync flags.
  void _createTables() {
    _db.execute('PRAGMA journal_mode = WAL;');
    _db.execute('PRAGMA synchronous = NORMAL;');

    _db.execute('''
      CREATE TABLE IF NOT EXISTS receipt_entries (
        entry_id TEXT PRIMARY KEY,
        is_synced INTEGER NOT NULL DEFAULT 0,
        synced_at TEXT,
        receipt_id TEXT NOT NULL,
        receipt_date TEXT NOT NULL,
        merchant TEXT NOT NULL,
        item TEXT NOT NULL,
        brand TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL,
        quantity REAL NOT NULL,
        pack_size REAL NOT NULL DEFAULT 1.0,
        unit TEXT NOT NULL,
        unit_price REAL NOT NULL,
        currency TEXT NOT NULL,
        discount REAL NOT NULL DEFAULT 0.0,
        fee REAL NOT NULL DEFAULT 0.0,
        tax REAL NOT NULL DEFAULT 0.0,
        deposit REAL NOT NULL DEFAULT 0.0,
        paid_total REAL NOT NULL,
        event_type TEXT NOT NULL,
        store_tier TEXT NOT NULL DEFAULT 'A',
        store_rating REAL NOT NULL DEFAULT 5.0,
        brand_tier TEXT NOT NULL DEFAULT 'A',
        brand_rating REAL NOT NULL DEFAULT 5.0,
        product_tier TEXT NOT NULL DEFAULT 'A',
        product_rating REAL NOT NULL DEFAULT 5.0,
        availability TEXT NOT NULL DEFAULT 'in_stock',
        notes TEXT NOT NULL DEFAULT '',
        recorded_at TEXT NOT NULL,
        account TEXT NOT NULL DEFAULT 'default:checking'
      );
    ''');

    _db.execute('CREATE INDEX IF NOT EXISTS idx_re_is_synced ON receipt_entries(is_synced);');
    _db.execute('CREATE INDEX IF NOT EXISTS idx_re_receipt_date ON receipt_entries(receipt_date);');
    _db.execute('CREATE INDEX IF NOT EXISTS idx_re_category ON receipt_entries(category);');
  }

  /// Insert a single receipt entry.
  void insertEntry(ReceiptEntryModel entry) {
    insertEntries([entry]);
  }

  /// Insert a batch of receipt entries within an atomic transaction.
  void insertEntries(List<ReceiptEntryModel> entries) {
    if (entries.isEmpty) return;

    final stmt = _db.prepare('''
      INSERT OR REPLACE INTO receipt_entries (
        entry_id, is_synced, synced_at, receipt_id, receipt_date,
        merchant, item, brand, category, quantity,
        pack_size, unit, unit_price, currency, discount,
        fee, tax, deposit, paid_total, event_type,
        store_tier, store_rating, brand_tier, brand_rating, product_tier,
        product_rating, availability, notes, recorded_at, account
      ) VALUES (
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?
      )
    ''');

    try {
      _db.execute('BEGIN TRANSACTION;');
      for (final e in entries) {
        final map = e.toSqliteMap();
        stmt.execute([
          map['entry_id'],
          map['is_synced'],
          map['synced_at'],
          map['receipt_id'],
          map['receipt_date'],
          map['merchant'],
          map['item'],
          map['brand'],
          map['category'],
          map['quantity'],
          map['pack_size'],
          map['unit'],
          map['unit_price'],
          map['currency'],
          map['discount'],
          map['fee'],
          map['tax'],
          map['deposit'],
          map['paid_total'],
          map['event_type'],
          map['store_tier'],
          map['store_rating'],
          map['brand_tier'],
          map['brand_rating'],
          map['product_tier'],
          map['product_rating'],
          map['availability'],
          map['notes'],
          map['recorded_at'],
          map['account'],
        ]);
      }
      _db.execute('COMMIT;');
    } catch (e) {
      _db.execute('ROLLBACK;');
      rethrow;
    } finally {
      stmt.dispose();
    }
  }

  /// Retrieve all entries that are pending desktop synchronization (`is_synced = 0`).
  List<ReceiptEntryModel> getPendingSyncEntries() {
    final rs = _db.select(
      'SELECT * FROM receipt_entries WHERE is_synced = 0 ORDER BY receipt_date ASC, recorded_at ASC',
    );
    return rs.map((row) => ReceiptEntryModel.fromSqliteMap(Map<String, dynamic>.from(row))).toList();
  }

  /// Mark specific entry IDs as synced, setting `is_synced = 1` and recording timestamp.
  void markEntriesSynced(List<String> entryIds, {String? syncedAt}) {
    if (entryIds.isEmpty) return;

    final timestamp = syncedAt ?? DateTime.now().toUtc().toIso8601String();
    final stmt = _db.prepare(
      'UPDATE receipt_entries SET is_synced = 1, synced_at = ? WHERE entry_id = ?',
    );

    try {
      _db.execute('BEGIN TRANSACTION;');
      for (final id in entryIds) {
        stmt.execute([timestamp, id]);
      }
      _db.execute('COMMIT;');
    } catch (e) {
      _db.execute('ROLLBACK;');
      rethrow;
    } finally {
      stmt.dispose();
    }
  }

  /// Retrieve all entries sorted chronologically descending (most recent first).
  List<ReceiptEntryModel> getAllEntries({int? limit, int? offset}) {
    String sql = 'SELECT * FROM receipt_entries ORDER BY receipt_date DESC, recorded_at DESC';
    if (limit != null) {
      sql += ' LIMIT $limit';
      if (offset != null) {
        sql += ' OFFSET $offset';
      }
    }
    final rs = _db.select(sql);
    return rs.map((row) => ReceiptEntryModel.fromSqliteMap(Map<String, dynamic>.from(row))).toList();
  }

  /// Retrieve entries filtered by month (YYYY-MM).
  List<ReceiptEntryModel> getEntriesByMonth(String month) {
    final rs = _db.select(
      'SELECT * FROM receipt_entries WHERE receipt_date LIKE ? ORDER BY receipt_date DESC',
      ['$month%'],
    );
    return rs.map((row) => ReceiptEntryModel.fromSqliteMap(Map<String, dynamic>.from(row))).toList();
  }

  /// Retrieve count of pending unsynced entries.
  int getPendingCount() {
    final rs = _db.select('SELECT COUNT(*) as cnt FROM receipt_entries WHERE is_synced = 0');
    if (rs.isEmpty) return 0;
    return rs.first['cnt'] as int;
  }

  /// Retrieve total count of entries.
  int getTotalCount() {
    final rs = _db.select('SELECT COUNT(*) as cnt FROM receipt_entries');
    if (rs.isEmpty) return 0;
    return rs.first['cnt'] as int;
  }

  /// Delete an entry by entryId
  void deleteEntry(String entryId) {
    _db.execute('DELETE FROM receipt_entries WHERE entry_id = ?', [entryId]);
  }

  /// Close database connection
  void close() {
    _db.dispose();
  }
}
