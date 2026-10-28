package init.peit.ui.verification

import init.peit.domain.model.ParsedReceiptItem
import java.math.BigDecimal
import java.math.BigInteger
import java.math.RoundingMode

data class ItemMoneyAllocation(
    val discount: BigDecimal,
    val tax: BigDecimal,
    val fee: BigDecimal,
    val deposit: BigDecimal,
    val paidTotal: BigDecimal
)

object ReceiptMoneyAllocator {
    private val zero = BigDecimal.ZERO.setScale(2)

    fun money(value: Double): BigDecimal {
        require(value.isFinite()) { "Money values must be finite" }
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP)
    }

    fun expectedPaidTotal(
        items: List<ParsedReceiptItem>,
        discount: Double,
        tax: Double,
        fee: Double,
        deposit: Double
    ): BigDecimal {
        require(items.isNotEmpty()) { "Add at least one receipt item" }
        val lines = items.map {
            require(it.quantity.isFinite() && it.quantity > 0.0) { "Item quantities must be finite and positive" }
            require(it.unitPrice.isFinite() && it.unitPrice >= 0.0) { "Item unit prices must be finite and non-negative" }
            require(it.linePrice.isFinite() && it.linePrice >= 0.0) { "Item line totals must be finite and non-negative" }
            money(it.linePrice)
        }
        require(lines.any { it > BigDecimal.ZERO }) { "Receipt needs a positive item subtotal" }
        val discountAmount = money(discount)
        val taxAmount = money(tax)
        val feeAmount = money(fee)
        val depositAmount = money(deposit)
        require(discountAmount >= BigDecimal.ZERO) { "Discount must be non-negative" }
        require(taxAmount <= BigDecimal.ZERO && feeAmount <= BigDecimal.ZERO && depositAmount <= BigDecimal.ZERO) {
            "Tax, fee, and deposit must use canonical non-positive signs"
        }
        val itemsTotal = lines.fold(zero) { sum, line -> sum + line }
        require(discountAmount <= itemsTotal) { "Discount cannot exceed positive item subtotals" }
        return itemsTotal - discountAmount - taxAmount - feeAmount - depositAmount
    }

    fun allocate(
        items: List<ParsedReceiptItem>,
        discount: Double,
        tax: Double,
        fee: Double,
        deposit: Double,
        paidTotal: Double
    ): List<ItemMoneyAllocation> {
        val expected = expectedPaidTotal(items, discount, tax, fee, deposit)
        require(expected > BigDecimal.ZERO) { "Calculated receipt total must be positive" }
        val observed = money(kotlin.math.abs(paidTotal))
        require(observed > BigDecimal.ZERO) { "Observed paid total must be non-zero" }
        require(expected.compareTo(observed) == 0) {
            "Receipt is out of balance: calculated ${expected.toPlainString()} but observed ${observed.toPlainString()}"
        }

        val lineAmounts = items.map { money(it.linePrice) }
        val discountShares = allocateComponent(money(discount), lineAmounts)
        val taxShares = allocateComponent(money(tax).abs(), lineAmounts).map { it.negate() }
        val feeShares = allocateComponent(money(fee).abs(), lineAmounts).map { it.negate() }
        val depositShares = allocateComponent(money(deposit).abs(), lineAmounts).map { it.negate() }

        return items.indices.map { index ->
            val itemPaid = lineAmounts[index] -
                discountShares[index] -
                taxShares[index] -
                feeShares[index] -
                depositShares[index]
            require(itemPaid >= BigDecimal.ZERO) { "Allocated discount exceeds item ${index + 1} subtotal" }
            ItemMoneyAllocation(
                discount = discountShares[index],
                tax = taxShares[index],
                fee = feeShares[index],
                deposit = depositShares[index],
                paidTotal = itemPaid.negate()
            )
        }
    }

    private fun allocateComponent(amount: BigDecimal, weights: List<BigDecimal>): List<BigDecimal> {
        val positiveIndexes = weights.indices.filter { weights[it] > BigDecimal.ZERO }
        if (amount.compareTo(BigDecimal.ZERO) == 0) return List(weights.size) { zero }
        require(positiveIndexes.isNotEmpty()) { "Cannot allocate an adjustment without positive item subtotals" }

        val amountCents = amount.movePointRight(2).toBigIntegerExact()
        val totalWeight = positiveIndexes.fold(BigDecimal.ZERO) { sum, index -> sum + weights[index] }
        val sharesInCents = MutableList(weights.size) { BigInteger.ZERO }
        var allocatedCents = BigInteger.ZERO
        positiveIndexes.dropLast(1).forEach { index ->
            val share = BigDecimal(amountCents)
                .multiply(weights[index])
                .divide(totalWeight, 0, RoundingMode.HALF_UP)
                .toBigIntegerExact()
            sharesInCents[index] = share
            allocatedCents += share
        }
        sharesInCents[positiveIndexes.last()] = amountCents - allocatedCents
        return sharesInCents.map { BigDecimal(it).movePointLeft(2).setScale(2) }
    }
}
