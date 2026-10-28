package init.peit.ui.verification

import init.peit.domain.model.ParsedReceiptItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReceiptReviewStateTest {
    @Test
    fun emptyReviewHasUnavailableTotalsNotANumericSentinel() {
        val state = ReceiptVerificationUiState()

        assertFalse(state.hasReceiptInput)
        assertNull(state.calculatedTotal)
        assertNull(state.absPaidTotal)
        assertNull(state.discrepancy)
        assertEquals("Add at least one receipt item", state.balanceCalculation.errorMessage)
        assertFalse(state.isBalanced)
        assertFalse(state.canSave)
    }

    @Test
    fun nonFiniteLineTotalsExposeTheValidationFailure() {
        listOf(Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY).forEach { invalid ->
            val state = state(linePrice = invalid)

            assertNull(state.calculatedTotal)
            assertNull(state.discrepancy)
            assertTrue(state.balanceCalculation.errorMessage.orEmpty().contains("finite"))
            assertFalse(state.isBalanced)
            assertFalse(state.canSave)
        }
    }

    @Test
    fun nonFiniteObservedPaymentIsUnavailableAndCannotSave() {
        listOf(Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY).forEach { invalid ->
            val state = state().copy(paidTotal = invalid)

            assertEquals(1.0, state.calculatedTotal!!, 0.0)
            assertNull(state.absPaidTotal)
            assertNull(state.discrepancy)
            assertFalse(state.isBalanced)
            assertFalse(state.canSave)
        }
    }

    @Test
    fun invalidAdjustmentsExposeTheirCauseRatherThanZeroChange() {
        val state = state().copy(discount = 2.0)

        assertNull(state.calculatedTotal)
        assertNull(state.discrepancy)
        assertEquals("Discount cannot exceed positive item subtotals", state.balanceCalculation.errorMessage)
        assertFalse(state.isBalanced)
        assertFalse(state.canSave)
    }

    @Test
    fun aggregateOverflowIsUnavailableRatherThanInfinity() {
        val item = ParsedReceiptItem(
            itemName = "Large amount",
            unitPrice = Double.MAX_VALUE,
            linePrice = Double.MAX_VALUE
        )
        val state = state().copy(items = listOf(item, item))

        assertNull(state.calculatedTotal)
        assertNull(state.discrepancy)
        assertNotNull(state.balanceCalculation.errorMessage)
        assertFalse(state.isBalanced)
    }

    @Test
    fun validCentRoundedBalanceRetainsExistingSaveRules() {
        val state = state().copy(
            items = listOf(
                ParsedReceiptItem(itemName = "A", unitPrice = 0.1, linePrice = 0.1),
                ParsedReceiptItem(itemName = "B", unitPrice = 0.2, linePrice = 0.2)
            ),
            paidTotal = -0.3
        )

        assertEquals(0.3, state.calculatedTotal!!, 0.0)
        assertEquals(0.3, state.absPaidTotal!!, 0.0)
        assertEquals(0.0, state.discrepancy!!, 0.0)
        assertNull(state.balanceCalculation.errorMessage)
        assertTrue(state.isBalanced)
        assertTrue(state.canSave)
        assertFalse(state.copy(labelsReviewed = false).canSave)
    }

    @Test
    fun incompleteManualEntryDoesNotReportAZeroBalance() {
        val state = state(linePrice = 0.0).copy(paidTotal = 0.0)

        assertTrue(state.hasReceiptInput)
        assertNull(state.calculatedTotal)
        assertNull(state.discrepancy)
        assertFalse(state.isBalanced)
        assertFalse(state.canSave)
    }

    @Test
    fun unavailableMoneyNeverFormatsNanOrInfinityAsCurrency() {
        listOf(null, Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY).forEach {
            assertEquals("Not available", formatReviewMoney(it, "USD $"))
        }
        assertEquals("USD $1.25", formatReviewMoney(1.25, "USD $"))
        assertEquals("+USD $0.25", formatReviewMoney(0.25, "USD $", signed = true))
        assertEquals("\u2212USD $0.25", formatReviewMoney(-0.25, "USD $", signed = true))
    }

    private fun state(linePrice: Double = 1.0) = ReceiptVerificationUiState(
        merchant = "Synthetic Market",
        date = "2026-10-22",
        labelsReviewed = true,
        items = listOf(ParsedReceiptItem(itemName = "Rice", unitPrice = 1.0, linePrice = linePrice)),
        paidTotal = 1.0
    )
}
