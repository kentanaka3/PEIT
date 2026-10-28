package init.peit

import init.peit.data.local.entity.ReceiptEntity
import init.peit.domain.engine.EconometricEngine
import init.peit.domain.model.IndexStatus
import init.peit.domain.model.TimePeriod
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EconometricEngineTest {

    private val basePeriod = TimePeriod.ofMonth("2026-01")
    private val currentPeriod = TimePeriod.ofMonth("2026-02")

    @Test
    fun priceIndex_matchesPythonAndFlutterEqualWeightFormula_notQuantityWeightedIndex() {
        val base = listOf(
            receipt("a-1", "A", 1.0, 10.0, 1_000.0, "2026-01-01"),
            receipt("a-2", "a", 3.0, 20.0, -1.0, "2026-01-02"),
            receipt("b-1", "B", 1.0, 100.0, 2.0, "2026-01-03")
        )
        val current = listOf(
            receipt("a-3", "A", 1.0, 35.0, 2.0, "2026-02-01"),
            receipt("a-4", "a", 3.0, 35.0, 2.0, "2026-02-02"),
            receipt("b-2", "B", 1.0, 50.0, 2.0, "2026-02-03")
        )

        val result = EconometricEngine.calculateIndices(
            base,
            current,
            basePeriod,
            currentPeriod
        )

        // Monthly prices: A = (1*10 + 3*20)/4 = 17.5, B = 100.
        // Price relatives are 35/17.5 = 2 and 50/100 = 0.5.
        // Equal-weight index = 100 * (2 + 0.5)/2 = 125.
        // A base-quantity-weighted index would instead be 170, so this
        // fixture distinguishes the selected matched-item formula.
        assertEquals(2, result.matchedItemCount)
        assertEquals(2, result.baseItemCount)
        assertEquals(100.0, result.coveragePercent, 0.0)
        assertEquals(125.0, result.priceIndex!!, 0.000001)
        assertEquals(25.0, result.priceChangePercentage!!, 0.000001)
        assertEquals(17.5, result.itemDetails.first { it.itemKey == "a" }.basePrice, 0.000001)
        assertEquals(IndexStatus.AVAILABLE, result.status)
    }

    @Test
    fun coverageIsMatchedItemsDividedByBaseItems() {
        val base = listOf(
            receipt("b1", "Apple", 1.0, 2.0, 2.0, "2026-01-01"),
            receipt("b2", "Bread", 1.0, 3.0, 3.0, "2026-01-02"),
            receipt("b3", "Milk", 1.0, 4.0, 4.0, "2026-01-03")
        )
        val current = listOf(
            receipt("c1", "Bread", 1.0, 3.3, 3.3, "2026-02-01")
        )

        val result = EconometricEngine.calculateIndices(base, current, basePeriod, currentPeriod)

        assertEquals(1, result.matchedItemCount)
        assertEquals(3, result.baseItemCount)
        assertEquals(33.33, result.coveragePercent, 0.0)
        assertEquals(110.0, result.priceIndex!!, 0.000001)
    }

    @Test
    fun expenditureUsesAbsolutePaidTotalAndIsSeparateFromUnitPriceIndex() {
        val base = listOf(
            receipt("b", "Coffee", 1.0, 10.0, -10.0, "2026-01-01")
        )
        val current = listOf(
            receipt("c", "Coffee", 1.0, 10.0, 50.0, "2026-02-01")
        )

        val result = EconometricEngine.calculateIndices(base, current, basePeriod, currentPeriod)

        assertEquals(100.0, result.priceIndex!!, 0.0)
        assertEquals(0.0, result.priceChangePercentage!!, 0.0)
        assertEquals(500.0, result.expenditureIndex!!, 0.0)
        assertEquals(400.0, result.expenditureChangePercentage!!, 0.0)
        assertEquals(50.0, result.expenditure!!, 0.0)
    }

    @Test
    fun zeroBaseExpenditureHasAnExplicitInvalidDenominatorState() {
        val result = EconometricEngine.calculateIndices(
            listOf(receipt("base", "Coffee", 1.0, 10.0, 0.0, "2026-01-01")),
            listOf(receipt("current", "Coffee", 1.0, 12.0, 5.0, "2026-02-01")),
            basePeriod,
            currentPeriod
        )

        assertEquals(IndexStatus.AVAILABLE, result.status)
        assertEquals(120.0, result.priceIndex!!, 0.0)
        assertEquals(IndexStatus.INVALID_DENOMINATOR, result.expenditureStatus)
        assertNull(result.expenditureIndex)
        assertNull(result.expenditureChangePercentage)
    }

    @Test
    fun noMatchesAndInvalidPriceDenominatorsDoNotReturnDefaultIndexOrChange() {
        val noMatch = EconometricEngine.calculateIndices(
            listOf(receipt("b", "Apple", 1.0, 2.0, 2.0, "2026-01-01")),
            listOf(receipt("c", "Banana", 1.0, 3.0, 3.0, "2026-02-01")),
            basePeriod,
            currentPeriod
        )
        assertEquals(IndexStatus.NO_MATCHES, noMatch.status)
        assertNull(noMatch.priceIndex)
        assertNull(noMatch.priceChangePercentage)

        val invalidBasePrice = EconometricEngine.calculateIndices(
            listOf(
                receipt("zero", "Zero", 1.0, 0.0, 2.0, "2026-01-01"),
                receipt("negative", "Negative", 1.0, -2.0, 2.0, "2026-01-02")
            ),
            listOf(receipt("positive", "Zero", 1.0, 1.0, 2.0, "2026-02-01")),
            basePeriod,
            currentPeriod
        )
        assertEquals(IndexStatus.INVALID_DENOMINATOR, invalidBasePrice.status)
        assertNull(invalidBasePrice.priceIndex)
        assertNull(invalidBasePrice.priceChangePercentage)
        assertTrue(invalidBasePrice.itemDetails.isEmpty())
    }

    @Test
    fun onlyPositiveUnitPricesAreUsedForMonthlyPriceAggregation() {
        val basket = EconometricEngine.aggregateReceiptsToBasketItems(
            listOf(
                receipt("valid", "Tea", 2.0, 5.0, 100.0, "2026-01-01"),
                receipt("zero", "Tea", 100.0, 0.0, 100.0, "2026-01-02"),
                receipt("negative", "Tea", 100.0, -5.0, 100.0, "2026-01-03")
            )
        )

        assertEquals(1, basket.size)
        assertEquals(2.0, basket.single().totalQuantity, 0.0)
        assertEquals(5.0, basket.single().averageUnitPrice, 0.0)
    }

    @Test
    fun onlyRecurringAndOneOffConfirmedConsumptionTypesAreIncluded() {
        val base = listOf(
            receipt("oneoff", "One-off", 1.0, 2.0, 2.0, "2026-01-01", eventType = "one_off"),
            receipt("subscription", "Subscription", 1.0, 3.0, 3.0, "2026-01-02", eventType = "recurring"),
            receipt("transfer", "Transfer", 1.0, 10.0, 10.0, "2026-01-03", eventType = "transfer"),
            receipt("refund", "Refund", 1.0, 20.0, 20.0, "2026-01-04", eventType = "refund")
        )
        val current = listOf(
            receipt("oneoff-current", "One-off", 1.0, 4.0, 4.0, "2026-02-01", eventType = "one_off"),
            receipt("subscription-current", "Subscription", 1.0, 6.0, 6.0, "2026-02-02", eventType = "recurring")
        )

        val result = EconometricEngine.calculateIndices(base, current, basePeriod, currentPeriod)

        assertEquals(2, result.baseItemCount)
        assertEquals(2, result.currentItemCount)
        assertEquals(2, result.matchedItemCount)
        assertEquals(200.0, result.priceIndex!!, 0.0)
    }

    @Test
    fun mixedCurrenciesReturnExplicitStatusWithoutConversion() {
        val base = listOf(
            receipt("b1", "Coffee", 1.0, 10.0, 10.0, "2026-01-01", currency = "USD"),
            receipt("b2", "Tea", 1.0, 5.0, 5.0, "2026-01-02", currency = "CAD")
        )
        val current = listOf(
            receipt("c1", "Coffee", 1.0, 12.0, 12.0, "2026-02-01", currency = "USD")
        )

        val result = EconometricEngine.calculateIndices(base, current, basePeriod, currentPeriod)

        assertEquals(IndexStatus.CURRENCY_MISMATCH, result.status)
        assertEquals(IndexStatus.CURRENCY_MISMATCH, result.expenditureStatus)
        assertNull(result.priceIndex)
        assertNull(result.expenditureIndex)
        assertNull(result.currency)
    }

    @Test
    fun timePeriodRejectsInvalidMonthInsteadOfSilentlySubstitutingOne() {
        val error = runCatching { TimePeriod.ofMonth("2026-13") }.exceptionOrNull()
        assertTrue(error is IllegalArgumentException)
    }

    private fun receipt(
        id: String,
        item: String,
        quantity: Double,
        unitPrice: Double,
        paidTotal: Double,
        date: String,
        eventType: String = "recurring",
        currency: String = "USD"
    ) = ReceiptEntity(
        receiptId = id,
        item = item,
        quantity = quantity,
        unitPrice = unitPrice,
        paidTotal = paidTotal,
        currency = currency,
        eventType = eventType,
        receiptDate = date
    )
}
