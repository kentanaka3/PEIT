package init.peit.data.ocr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class OcrReceiptParserTest {

    private lateinit var parser: OcrReceiptParser

    @Before
    fun setUp() {
        parser = OcrReceiptParser()
    }

    @Test
    fun testParseMxnReceipt() {
        val mxnReceiptText = """
            WALMART SUPERCENTER
            RFC: WAL930902MS2
            FECHA: 22/10/2026
            LECHE LALA 1L          28.50
            PAN DULCE 500G        2 X 15.00
            ARROZ 1KG              32.00
            SUBTOTAL              90.50
            IVA 16%               14.48
            DESCUENTO              5.00
            FEE SERVICIO           2.00
            ENVASE DEPOSITO        1.50
            TOTAL PAGADO         103.48
        """.trimIndent()

        val parsed = parser.parseRawText(mxnReceiptText)

        assertEquals("MXN", parsed.currency)
        assertTrue(parsed.merchant.contains("WALMART"))
        assertEquals("2026-10-22", parsed.date)
        assertEquals(-14.48, parsed.tax, 0.01)
        assertEquals(5.00, parsed.discount, 0.01)
        assertEquals(-2.00, parsed.fee, 0.01)
        assertEquals(-1.50, parsed.deposit, 0.01)
        assertEquals(103.48, parsed.paidTotal, 0.01)
        assertTrue(parsed.items.isNotEmpty())
        val quantityLine = parsed.items.first { it.itemName.contains("PAN DULCE") }
        assertEquals(2.0, quantityLine.quantity, 0.0)
        assertEquals(15.0, quantityLine.unitPrice, 0.0)
        assertEquals(30.0, quantityLine.linePrice, 0.0)
    }

    @Test
    fun testParseUsdReceipt() {
        val usdReceiptText = """
            TARGET STORES
            DATE: 2026-10-22
            ORGANIC MILK 1L        4.50
            APPLE JUICE 12OZ       3.20
            CEREAL BOX 500G        5.00
            SUBTOTAL              12.70
            TAX                    1.02
            DISCOUNT               1.00
            TOTAL                 12.72
        """.trimIndent()

        val parsed = parser.parseRawText(usdReceiptText)

        assertEquals("USD", parsed.currency)
        assertTrue(parsed.merchant.contains("TARGET"))
        assertEquals("2026-10-22", parsed.date)
        assertEquals(-1.02, parsed.tax, 0.01)
        assertEquals(1.00, parsed.discount, 0.01)
        assertEquals(12.72, parsed.paidTotal, 0.01)
        assertEquals(3, parsed.items.size)
    }

    @Test
    fun testParseEurReceipt() {
        val eurReceiptText = """
            CARREFOUR
            DATE: 22/10/2026
            BAGUETTE 250G          1.20 €
            CHEESE 200G            3.80 €
            SUBTOTAL               5.00 €
            VAT                    0.50 €
            TOTAL                  5.50 €
        """.trimIndent()

        val parsed = parser.parseRawText(eurReceiptText)

        assertEquals("EUR", parsed.currency)
        assertTrue(parsed.merchant.contains("CARREFOUR"))
        assertEquals("2026-10-22", parsed.date)
        assertEquals(-0.50, parsed.tax, 0.01)
        assertEquals(5.50, parsed.paidTotal, 0.01)
    }

    @Test
    fun testItemPackSizeAndUnitParsing() {
        val itemText = """
            SORIANA
            FECHA: 22/10/2026
            ACEITE NUTRIOLI 1L     45.00
            JABON ZOTE 500G        18.00
            TOTAL                  63.00
        """.trimIndent()

        val parsed = parser.parseRawText(itemText)
        val oil = parsed.items.find { it.itemName.contains("NUTRIOLI") }
        assertNotNull(oil)
        assertEquals("1 l", oil?.packSize?.lowercase())
        assertEquals("l", oil?.unit?.lowercase())

        val soap = parsed.items.find { it.itemName.contains("ZOTE") }
        assertNotNull(soap)
        assertEquals("500 g", soap?.packSize?.lowercase())
        assertEquals("g", soap?.unit?.lowercase())
    }

    @Test
    fun missingDateStaysUnknownAndTrailingEurDecimalCommaIsParsed() {
        val parsed = parser.parseRawText(
            """
                LIDL
                MILCH 1L 1,20 EUR
                TOTAL 1,20 EUR
            """.trimIndent()
        )

        assertEquals("", parsed.date)
        assertEquals("EUR", parsed.currency)
        assertEquals(1.20, parsed.paidTotal, 0.0)
        assertEquals(1, parsed.items.size)
        assertEquals(1.20, parsed.items.single().linePrice, 0.0)
        assertEquals(1.20, parsed.items.single().unitPrice, 0.0)
    }

    @Test
    fun missingObservedTotalIsNotReconciledFromItems() {
        val parsed = parser.parseRawText(
            """
                TARGET
                DATE: 2026-10-22
                SOAP 2.00
            """.trimIndent()
        )

        assertEquals(0.0, parsed.paidTotal, 0.0)
    }
}
