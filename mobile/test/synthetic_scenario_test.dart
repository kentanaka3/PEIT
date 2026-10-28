import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';

import '../lib/models/receipt_entry.dart';
import '../lib/services/econometric_engine.dart';

const _contractRelativePath = 'config/scenarios/alice_bob.json';
const _roundingTolerance = 0.000001;
const _canonicalColumns = <String>[
  'receipt_id',
  'receipt_date',
  'merchant',
  'item',
  'brand',
  'category',
  'quantity',
  'pack_size',
  'unit',
  'unit_price',
  'currency',
  'discount',
  'fee',
  'tax',
  'deposit',
  'paid_total',
  'event_type',
  'store_tier',
  'store_rating',
  'brand_tier',
  'brand_rating',
  'product_tier',
  'product_rating',
  'availability',
  'notes',
];

void main() {
  final contract = _loadContract();
  final personas = _requiredObject(contract, 'personas');

  for (final name in ['alice', 'bob']) {
    final persona = _requiredObject(personas, name);
    final rows = _requiredRows(persona, 'rows');
    final identity = _requiredObject(persona, 'identity');

    test('$name shared synthetic golden metrics', () {
      expect(persona['fictional_synthetic_example'], isTrue);
      expect(rows, isNotEmpty);
      for (final row in rows) {
        expect(row.keys.toSet(), equals(_canonicalColumns.toSet()));
        expect(_stringValue(row, 'currency'), equals('MXN'));
        expect(_numberValue(row, 'pack_size'), equals(1));
        expect(_stringValue(row, 'item'), matches(RegExp(r'^[a-z0-9 ]+$')));
      }

      final entries = rows.map(_toEntry).toList();
      final actual = EconometricEngine.calculateMonthlyIndices(entries);
      final expectedMetrics = _requiredObject(persona, 'expected_metrics');
      final expectedPeriods = _requiredList(expectedMetrics, 'periods');

      expect(actual, hasLength(expectedPeriods.length));
      for (var index = 0; index < expectedPeriods.length; index++) {
        final expected = _object(expectedPeriods[index]);
        final result = actual[index];
        expect(result.month, equals(_stringValue(expected, 'month')));
        expect(
          result.expenditure,
          closeTo(_numberValue(expected, 'expenditure'), _roundingTolerance),
        );
        expect(
          result.fixedBasketIndex,
          closeTo(_numberValue(expected, 'price_index'), _roundingTolerance),
        );
        expect(
          result.changingBasketExpenditureIndex,
          closeTo(
            _numberValue(expected, 'expenditure_index'),
            _roundingTolerance,
          ),
        );
        expect(
          result.coveragePercent,
          closeTo(
            _numberValue(expected, 'coverage_percent'),
            _roundingTolerance,
          ),
        );
      }
    });

    test('$name synthetic row and account provenance stay isolated', () {
      final prefix = _stringValue(identity, 'receipt_id_prefix');
      final account = _stringValue(identity, 'account');
      final ids = rows.map((row) => _stringValue(row, 'receipt_id')).toSet();
      expect(ids, hasLength(rows.length));
      expect(ids.every((id) => id.startsWith(prefix)), isTrue);
      expect(account, startsWith('synthetic:$name:'));
      final entries = rows.map((row) => _toEntry(row, account: account)).toList();
      expect(entries.map((entry) => entry.receiptId).toSet(), equals(ids));
      expect(entries.every((entry) => entry.account == account), isTrue);
      expect(
        entries.every((entry) => entry.entryId.isNotEmpty && !entry.isSynced),
        isTrue,
      );
    });
  }

  final characterization = _requiredObject(contract, 'characterization');
  test('no-match case reports missing price relatives without parity claims', () {
    final noMatch = _requiredObject(characterization, 'no_match');
    final base = _requiredRows(noMatch, 'base_rows').map(_toEntry).toList();
    final current = _requiredRows(noMatch, 'current_rows')
        .map(_toEntry)
        .toList();
    final records = EconometricEngine.calculateMonthlyIndices(
      [...base, ...current],
    );

    expect(records, hasLength(2));
    expect(records.last.fixedBasketIndex, isNull);
    expect(records.last.coveragePercent, equals(0));
    expect(records.last.status, equals('derived'));
    expect(
      _requiredObject(noMatch, 'platform_characterization')['native_engine'],
      contains('NO_MATCHES'),
    );
  });

  test('single available month is not labelled insufficient by Dart engine', () {
    final insufficient = _requiredObject(characterization, 'insufficient_history');
    final base =
        _requiredRows(insufficient, 'base_rows').map(_toEntry).toList();
    final records = EconometricEngine.calculateMonthlyIndices(base);

    expect(records, hasLength(1));
    expect(records.single.fixedBasketIndex, equals(100));
    expect(records.single.status, equals('derived'));
  });

  test('mixed-currency behavior is characterized separately', () {
    final mismatch = _requiredObject(characterization, 'currency_mismatch');
    final rows = [
      ..._requiredRows(mismatch, 'base_rows'),
      ..._requiredRows(mismatch, 'current_rows'),
    ];
    final records =
        EconometricEngine.calculateMonthlyIndices(rows.map(_toEntry));
    final expected = _requiredObject(
      mismatch,
      'expected_for_python_and_flutter',
    );

    expect(
      records.last.fixedBasketIndex,
      closeTo(_numberValue(expected, 'price_index'), _roundingTolerance),
    );
    expect(
      records.last.coveragePercent,
      equals(_numberValue(expected, 'coverage_percent')),
    );
    expect(
      _requiredObject(mismatch, 'expected_for_native')['status'],
      equals('CURRENCY_MISMATCH'),
    );
  });
}

Map<String, dynamic> _loadContract() {
  var directory = Directory.current.absolute;
  while (true) {
    final candidate = File('${directory.path}/$_contractRelativePath');
    if (candidate.existsSync()) {
      final decoded = jsonDecode(candidate.readAsStringSync());
      return _object(decoded);
    }
    final parent = directory.parent;
    if (parent.path == directory.path) {
      throw FileSystemException(
        'Could not locate $_contractRelativePath from ${Directory.current.path}',
      );
    }
    directory = parent;
  }
}

Map<String, dynamic> _object(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map(
      (key, item) => MapEntry(key.toString(), item),
    );
  }
  throw FormatException('Expected a JSON object, found ${value.runtimeType}.');
}

Map<String, dynamic> _requiredObject(
  Map<String, dynamic> object,
  String key,
) {
  if (!object.containsKey(key)) {
    throw FormatException('Missing JSON object "$key".');
  }
  return _object(object[key]);
}

List<Object?> _requiredList(Map<String, dynamic> object, String key) {
  final value = object[key];
  if (value is List<Object?>) return value;
  throw FormatException('Expected JSON array "$key".');
}

List<Map<String, dynamic>> _requiredRows(
  Map<String, dynamic> object,
  String key,
) =>
    _requiredList(object, key).map(_object).toList();

String _stringValue(Map<String, dynamic> object, String key) {
  final value = object[key];
  if (value is String) return value;
  throw FormatException('Expected string "$key".');
}

double _numberValue(Map<String, dynamic> object, String key) {
  final value = object[key];
  if (value is num) return value.toDouble();
  throw FormatException('Expected number "$key".');
}

ReceiptEntryModel _toEntry(
  Map<String, dynamic> row, {
  String account = 'synthetic:characterization:checking',
}) =>
    ReceiptEntryModel.create(
      receiptId: _stringValue(row, 'receipt_id'),
      receiptDate: _stringValue(row, 'receipt_date'),
      merchant: _stringValue(row, 'merchant'),
      item: _stringValue(row, 'item'),
      brand: _stringValue(row, 'brand'),
      category: _stringValue(row, 'category'),
      quantity: _numberValue(row, 'quantity'),
      packSize: _numberValue(row, 'pack_size'),
      unit: _stringValue(row, 'unit'),
      unitPrice: _numberValue(row, 'unit_price'),
      currency: _stringValue(row, 'currency'),
      discount: _numberValue(row, 'discount'),
      fee: _numberValue(row, 'fee'),
      tax: _numberValue(row, 'tax'),
      deposit: _numberValue(row, 'deposit'),
      paidTotal: _numberValue(row, 'paid_total'),
      eventType: _stringValue(row, 'event_type'),
      storeTier: _stringValue(row, 'store_tier'),
      storeRating: _numberValue(row, 'store_rating'),
      brandTier: _stringValue(row, 'brand_tier'),
      brandRating: _numberValue(row, 'brand_rating'),
      productTier: _stringValue(row, 'product_tier'),
      productRating: _numberValue(row, 'product_rating'),
      availability: _stringValue(row, 'availability'),
      notes: _stringValue(row, 'notes'),
      recordedAt: '2024-02-29T12:00:00Z',
      account: account,
    );
