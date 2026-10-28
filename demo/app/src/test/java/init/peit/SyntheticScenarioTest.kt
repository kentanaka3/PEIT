package init.peit

import com.squareup.moshi.Json
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import init.peit.data.local.entity.ReceiptEntity
import init.peit.domain.engine.EconometricEngine
import init.peit.domain.model.IndexStatus
import init.peit.domain.model.TimePeriod
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files
import java.nio.file.Path

class SyntheticScenarioTest {

    @Test
    fun aliceSyntheticRowsMatchSharedGoldenMetrics() {
        assertPersonaGolden("alice")
    }

    @Test
    fun aliceSyntheticReceiptIdentityIsNamespacedAndNotSynced() {
        assertPersonaIdentity("alice")
    }

    @Test
    fun bobSyntheticRowsMatchSharedGoldenMetrics() {
        assertPersonaGolden("bob")
    }

    @Test
    fun bobSyntheticReceiptIdentityIsNamespacedAndNotSynced() {
        assertPersonaIdentity("bob")
    }

    @Test
    fun noMatchIsCharacterizedWithNativeStatusOnly() {
        val scenario = fixture().characterization.noMatch
        val result = calculate(scenario.baseRows, scenario.currentRows)

        assertEquals(IndexStatus.NO_MATCHES, result.status)
        assertNull(result.priceIndex)
        assertEquals(0.0, result.coveragePercent, 0.0)
    }

    @Test
    fun emptyCurrentPeriodIsCharacterizedAsInsufficientHistory() {
        val scenario = fixture().characterization.insufficientHistory
        val result = calculate(scenario.baseRows, scenario.currentRows)

        assertEquals(IndexStatus.INSUFFICIENT_HISTORY, result.status)
        assertNull(result.priceIndex)
        assertTrue(scenario.currentRows.isEmpty())
    }

    @Test
    fun mixedCurrencyCharacterizationDoesNotClaimSharedParity() {
        val scenario = fixture().characterization.currencyMismatch
        val result = calculate(scenario.baseRows, scenario.currentRows)

        assertEquals(IndexStatus.valueOf(scenario.expectedForNative.status), result.status)
        assertNull(result.priceIndex)
        assertNull(result.expenditureIndex)
    }

    private fun assertPersonaGolden(name: String) {
        val persona = fixture().personas.getValue(name)
        assertTrue(persona.fictionalSyntheticExample)
        val expectedPeriods = persona.expectedMetrics.periods
        assertEquals(2, expectedPeriods.size)

        val basePeriod = expectedPeriods.first()
        val currentPeriod = expectedPeriods.last()
        assertEquals(100.0, basePeriod.priceIndex, 0.000001)
        val baseRows = persona.rows.filter {
            it.receiptDate.startsWith(basePeriod.month)
        }
        val currentRows = persona.rows.filter {
            it.receiptDate.startsWith(currentPeriod.month)
        }
        val result = calculate(baseRows, currentRows)
        assertEquals(IndexStatus.AVAILABLE, result.status)
        assertEquals(IndexStatus.AVAILABLE, result.status)
        assertEquals(currentPeriod.priceIndex, result.priceIndex!!, 0.000001)
        assertEquals(
            currentPeriod.expenditureIndex,
            result.expenditureIndex!!,
            0.000001
        )
        assertEquals(
            currentPeriod.coveragePercent,
            result.coveragePercent,
            0.000001
        )
        assertEquals(currentPeriod.expenditure, result.expenditure!!, 0.000001)
    }

    private fun assertPersonaIdentity(name: String) {
        val persona = fixture().personas.getValue(name)
        val prefix = persona.identity.receiptIdPrefix
        val account = persona.identity.account
        val ids = persona.rows.map { it.receiptId }

        assertTrue(account.startsWith("synthetic:$name:"))
        assertEquals(ids.size, ids.toSet().size)
        assertTrue(ids.all { it.startsWith(prefix) })

        val entities = persona.rows.map(::toEntity)
        assertEquals(ids, entities.map { it.receiptId })
        assertTrue(entities.all { it.currency == persona.currency })
        assertTrue(entities.all { it.packSize == "1.0" })
        assertNotNull(persona.identity.provenance)
    }

    private fun calculate(
        baseRows: List<SyntheticReceiptRow>,
        currentRows: List<SyntheticReceiptRow>
    ) = EconometricEngine.calculateIndices(
        baseRows.map(::toEntity),
        currentRows.map(::toEntity),
        TimePeriod.ofMonth("2024-01"),
        TimePeriod.ofMonth("2024-02")
    )

    private fun toEntity(row: SyntheticReceiptRow) = ReceiptEntity(
        receiptId = row.receiptId,
        receiptDate = row.receiptDate,
        merchant = row.merchant,
        item = row.item,
        brand = row.brand,
        category = row.category,
        quantity = row.quantity,
        packSize = row.packSize.toString(),
        unit = row.unit,
        unitPrice = row.unitPrice,
        currency = row.currency,
        discount = row.discount,
        fee = row.fee,
        tax = row.tax,
        deposit = row.deposit,
        paidTotal = row.paidTotal,
        eventType = row.eventType,
        storeTier = row.storeTier,
        storeRating = row.storeRating,
        brandTier = row.brandTier,
        brandRating = row.brandRating,
        productTier = row.productTier,
        productRating = row.productRating,
        availability = row.availability,
        notes = row.notes
    )

    private fun fixture(): SyntheticScenarioFixture {
        val adapter = Moshi.Builder()
            .addLast(KotlinJsonAdapterFactory())
            .build()
            .adapter(SyntheticScenarioFixture::class.java)
        return adapter.fromJson(Files.readString(findContractPath()))
            ?: error("Synthetic scenario fixture decoded to null.")
    }

    private fun findContractPath(): Path {
        var directory = Path.of("").toAbsolutePath()
        while (true) {
            val candidate = directory.resolve("config/scenarios/alice_bob.json")
            if (Files.isRegularFile(candidate)) return candidate
            directory = directory.parent
                ?: error("Could not locate config/scenarios/alice_bob.json.")
        }
    }
}

private data class SyntheticScenarioFixture(
    val personas: Map<String, SyntheticPersona>,
    val characterization: SyntheticCharacterization
)

private data class SyntheticPersona(
    @Json(name = "fictional_synthetic_example")
    val fictionalSyntheticExample: Boolean,
    val currency: String,
    val identity: SyntheticIdentity,
    val rows: List<SyntheticReceiptRow>,
    @Json(name = "expected_metrics")
    val expectedMetrics: SyntheticExpectedMetrics
)

private data class SyntheticIdentity(
    @Json(name = "receipt_id_prefix")
    val receiptIdPrefix: String,
    val account: String,
    val provenance: String
)

private data class SyntheticExpectedMetrics(
    val periods: List<SyntheticExpectedPeriod>
)

private data class SyntheticExpectedPeriod(
    val month: String,
    val expenditure: Double,
    @Json(name = "price_index")
    val priceIndex: Double,
    @Json(name = "expenditure_index")
    val expenditureIndex: Double,
    @Json(name = "coverage_percent")
    val coveragePercent: Double
)

private data class SyntheticReceiptRow(
    @Json(name = "receipt_id")
    val receiptId: String,
    @Json(name = "receipt_date")
    val receiptDate: String,
    val merchant: String,
    val item: String,
    val brand: String,
    val category: String,
    val quantity: Double,
    @Json(name = "pack_size")
    val packSize: Double,
    val unit: String,
    @Json(name = "unit_price")
    val unitPrice: Double,
    val currency: String,
    val discount: Double,
    val fee: Double,
    val tax: Double,
    val deposit: Double,
    @Json(name = "paid_total")
    val paidTotal: Double,
    @Json(name = "event_type")
    val eventType: String,
    @Json(name = "store_tier")
    val storeTier: String,
    @Json(name = "store_rating")
    val storeRating: Double,
    @Json(name = "brand_tier")
    val brandTier: String,
    @Json(name = "brand_rating")
    val brandRating: Double,
    @Json(name = "product_tier")
    val productTier: String,
    @Json(name = "product_rating")
    val productRating: Double,
    val availability: String,
    val notes: String
)

private data class SyntheticCharacterization(
    @Json(name = "no_match")
    val noMatch: SyntheticCharacterizationCase,
    @Json(name = "insufficient_history")
    val insufficientHistory: SyntheticCharacterizationCase,
    @Json(name = "currency_mismatch")
    val currencyMismatch: SyntheticCurrencyCharacterization
)

private data class SyntheticCharacterizationCase(
    @Json(name = "base_rows")
    val baseRows: List<SyntheticReceiptRow>,
    @Json(name = "current_rows")
    val currentRows: List<SyntheticReceiptRow>
)

private data class SyntheticCurrencyCharacterization(
    @Json(name = "base_rows")
    val baseRows: List<SyntheticReceiptRow>,
    @Json(name = "current_rows")
    val currentRows: List<SyntheticReceiptRow>,
    @Json(name = "expected_for_native")
    val expectedForNative: SyntheticNativeExpected
)

private data class SyntheticNativeExpected(
    val status: String
)
