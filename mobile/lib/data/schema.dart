import 'package:drift/drift.dart';
import 'schema_constants.dart';

export 'schema_constants.dart';

/// Drift Table definition mirroring the strict 25-column PEIT receipt schema,
/// plus local synchronization metadata.
@DataClassName('ReceiptEntry')
class ReceiptEntriesTable extends Table {
  @override
  String get tableName => 'receipt_entries';

  // Primary key & sync tracking columns
  TextColumn get entryId => text()();
  BoolColumn get isSynced => boolean().withDefault(const Constant(false))();
  TextColumn get syncedAt => text().nullable()();

  // Core 25 columns from PEIT schema
  TextColumn get receiptId => text()();
  TextColumn get receiptDate => text()(); // YYYY-MM-DD
  TextColumn get merchant => text()();
  TextColumn get item => text()();
  TextColumn get brand => text().withDefault(const Constant(''))();
  TextColumn get category => text()();
  RealColumn get quantity => real()();
  RealColumn get packSize => real().withDefault(const Constant(1.0))();
  TextColumn get unit => text()();
  RealColumn get unitPrice => real()();
  TextColumn get currency => text().withLength(min: 3, max: 3)();
  RealColumn get discount => real().withDefault(const Constant(0.0))();
  RealColumn get fee => real().withDefault(const Constant(0.0))();
  RealColumn get tax => real().withDefault(const Constant(0.0))();
  RealColumn get deposit => real().withDefault(const Constant(0.0))();
  RealColumn get paidTotal => real()();
  TextColumn get eventType => text()(); // recurring, one_off, transfer, refund, income
  TextColumn get storeTier => text().withDefault(const Constant('A'))();
  RealColumn get storeRating => real().withDefault(const Constant(5.0))();
  TextColumn get brandTier => text().withDefault(const Constant('A'))();
  RealColumn get brandRating => real().withDefault(const Constant(5.0))();
  TextColumn get productTier => text().withDefault(const Constant('A'))();
  RealColumn get productRating => real().withDefault(const Constant(5.0))();
  TextColumn get availability => text().withDefault(const Constant('in_stock'))();
  TextColumn get notes => text().withDefault(const Constant(''))();
  TextColumn get recordedAt => text()();

  // Multi-account support
  TextColumn get account => text().withDefault(const Constant('default:checking'))();

  @override
  Set<Column> get primaryKey => {entryId};
}
