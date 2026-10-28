package init.peit

import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.util.ReceiptContract
import org.junit.Assert.assertEquals
import org.junit.Test
import java.lang.reflect.Modifier

class ReceiptSchemaTest {

    @Test
    fun receiptEntity_matchesCanonical25ColumnContract() {
        val expectedColumns = setOf(
            "receipt_id", "receipt_date", "merchant", "item", "brand", "category", "quantity",
            "pack_size", "unit", "unit_price", "currency", "discount", "fee", "tax", "deposit",
            "paid_total", "event_type", "store_tier", "store_rating", "brand_tier", "brand_rating",
            "product_tier", "product_rating", "availability", "notes"
        )
        // Compose adds a static $stable field; only instance fields represent stored receipt properties.
        val fields = ReceiptEntity::class.java.declaredFields
            .filterNot { Modifier.isStatic(it.modifiers) }

        assertEquals(25, fields.size)
        assertEquals(expectedColumns, fields.map { it.name.camelToSnakeCase() }.toSet())
        assertEquals(String::class.java, fields.single { it.name == "packSize" }.type)
        assertEquals(String::class.java, fields.single { it.name == "availability" }.type)
        listOf(
            "quantity", "unitPrice", "discount", "fee", "tax", "deposit", "paidTotal",
            "storeRating", "brandRating", "productRating"
        ).forEach { property ->
            assertEquals(Double::class.javaPrimitiveType, fields.single { it.name == property }.type)
        }
    }

    @Test
    fun omittedQualityFieldsUseExplicitlyProvisionalDefaults() {
        val receipt = ReceiptEntity()

        assertEquals("1", receipt.packSize)
        assertEquals("piece", receipt.unit)
        assertEquals("one_off", receipt.eventType)
        assertEquals("C", receipt.storeTier)
        assertEquals(3.0, receipt.storeRating, 0.0)
        assertEquals("C", receipt.brandTier)
        assertEquals(3.0, receipt.brandRating, 0.0)
        assertEquals("C", receipt.productTier)
        assertEquals(3.0, receipt.productRating, 0.0)
        assertEquals("in_stock", receipt.availability)
    }

    @Test
    fun packSizeIsStoredAsNumericTextWithUnitSeparate() {
        val canonical = ReceiptContract.canonicalize(
            ReceiptEntity(packSize = "500 g", unit = "g")
        )

        assertEquals("500", canonical.packSize)
        assertEquals("g", canonical.unit)
    }

    private fun String.camelToSnakeCase(): String =
        replace(Regex("([a-z0-9])([A-Z])"), "$1_$2").lowercase()
}
