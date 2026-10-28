import 'package:test/test.dart';
import '../lib/data/schema_constants.dart';
import '../lib/ocr/parser.dart';

void main() {
  group('Dart ReceiptParser & OCR Models', () {
    final parser = ReceiptParser(defaultCurrency: 'MXN');

    test('Bilingual date extraction handles ISO, DD/MM/YYYY, and Spanish month names', () {
      final receiptIso = parser.parseText('''
WALMART SUPERCENTER
2026-03-15
LECHE 1L 25.50
TOTAL 25.50
''');
      expect(receiptIso.receiptDate, equals('2026-03-15'));
      expect(receiptIso.merchant, equals('Walmart'));

      final receiptSlash = parser.parseText('''
SORIANA HIPER
15/03/2026
ARROZ 1KG 32.00
TOTAL 32.00
''');
      expect(receiptSlash.receiptDate, equals('2026-03-15'));
      expect(receiptSlash.merchant, equals('Soriana'));

      final receiptSpanishMonth = parser.parseText('''
OXXO
15 de marzo de 2026
AGUA 1L 15.00
TOTAL 15.00
''');
      expect(receiptSpanishMonth.receiptDate, equals('2026-03-15'));
      expect(receiptSpanishMonth.merchant, equals('OXXO'));
    });

    test('Bilingual currency detection resolves MXN, USD, and EUR', () {
      final rMxn = parser.parseText('''
BODEGA AURRERA
2026-01-10
TOTAL PESOS M.N. 120.00
''');
      expect(rMxn.currency, equals('MXN'));

      final rUsd = parser.parseText('''
TARGET
2026-01-10
TOTAL USD 45.00
''');
      expect(rUsd.currency, equals('USD'));

      final rEur = parser.parseText('''
CARREFOUR
2026-01-10
TOTAL EUR 38.50
''');
      expect(rEur.currency, equals('EUR'));
    });

    test('Spatial clustering and price pairing extracts line items accurately', () {
      final sampleReceipt = '''
WALMART SUPERCENTER #2241
2026-10-06
LECHE LALA ENTERA 1L 28.50
PAN BLANCO BIMBO 48.00
HUEVO BLANCO 12 PK 38.00
SUBTOTAL 114.50
DESCUENTO 10.00
TOTAL 104.50
''';

      final parsed = parser.parseText(sampleReceipt);

      expect(parsed.merchant, equals('Walmart'));
      expect(parsed.receiptDate, equals('2026-10-06'));
      expect(parsed.items.length, equals(3));

      final item1 = parsed.items[0];
      expect(item1.item, contains('LECHE LALA ENTERA 1L'));
      expect(item1.brand, equals('Lala'));
      expect(item1.category, equals('Food and beverages'));
      expect(item1.totalPrice, equals(28.50));
      expect(item1.unit, equals('L'));

      final item2 = parsed.items[1];
      expect(item2.item, contains('PAN BLANCO BIMBO'));
      expect(item2.brand, equals('Bimbo'));
      expect(item2.totalPrice, equals(48.00));

      final item3 = parsed.items[2];
      expect(item3.totalPrice, equals(38.00));

      expect(parsed.subtotal, equals(114.50));
      expect(parsed.discountTotal, equals(10.00));
      expect(parsed.paidTotal, equals(104.50));

      // Balance check: 114.50 - 10.00 = 104.50 -> balanceDelta == 0
      expect(parsed.isBalanced, isTrue);
      expect(parsed.balanceDelta, equals(0.0));
    });

    test('Multi-line quantity pairing (e.g. 2 x 15.00) properly updates line item', () {
      final sample = '''
SORIANA
2026-05-12
YOGURT NATURAL 1L
2 x 15.00
TOTAL 30.00
''';
      final parsed = parser.parseText(sample);
      expect(parsed.items.length, equals(1));
      final it = parsed.items.first;
      expect(it.quantity, equals(2.0));
      expect(it.unitPrice, equals(15.0));
      expect(it.totalPrice, equals(30.0));
      expect(parsed.isBalanced, isTrue);
    });

    test('toPeitRows outputs strictly conforming 25-column records with accounting signs', () {
      final sample = '''
COSTCO WHOLESALE
2026-08-20
KIRKLAND ACEITE 2L 85.00
TOTAL 85.00
''';
      final parsed = parser.parseText(sample);
      final rows = parsed.toPeitRows();

      expect(rows.length, equals(1));
      final row = rows.first;

      // Verify all 25 required schema columns exist
      for (final col in PeitSchemaConstants.requiredColumns) {
        expect(row.containsKey(col), isTrue, reason: 'Missing column: $col');
      }

      // Accounting sign check: paid_total must be negative for expenses
      expect(row['paid_total'], equals(-85.00));
      expect(row['discount'], equals(0.0));
      expect(row['tax'], equals(0.0));
      expect(row['fee'], equals(0.0));
      expect(row['deposit'], equals(0.0));
      expect(row['currency'], equals('MXN'));
      expect(row['merchant'], equals('Costco'));
      expect(row['store_tier'], equals('A'));
      expect(row['availability'], equals('in_stock'));
    });
  });
}
