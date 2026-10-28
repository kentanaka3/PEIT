package init.peit.domain.engine

import init.peit.data.local.entity.ReceiptEntity
import init.peit.domain.model.BasketItem
import init.peit.domain.model.InflationIndexResult
import init.peit.domain.model.IndexStatus
import init.peit.domain.model.ItemIndexDetail
import init.peit.domain.model.TimePeriod
import kotlin.math.abs
import kotlin.math.round

object EconometricEngine {
    private val consumptionTypes = setOf("recurring", "one_off")

    /**
     * Aggregates consumption observations by normalized item name.
     * Unit prices use quantity-weighted unit_price values; expenditure remains
     * a separate sum of absolute paid_total values.
     */
    fun aggregateReceiptsToBasketItems(receipts: List<ReceiptEntity>): List<BasketItem> {
        val grouped = receipts.asSequence()
            .filter(::isConsumption)
            .filter { it.item.isNotBlank() }
            .groupBy { normalizeItem(it.item) }

        return grouped.entries
            .sortedBy { it.key }
            .mapNotNull { (key, itemReceipts) ->
                val validPriceRows = itemReceipts.filter {
                    it.quantity.isFinite() && it.quantity > 0.0 &&
                        it.unitPrice.isFinite() && it.unitPrice > 0.0
                }
                val totalQuantity = validPriceRows.sumOf { it.quantity }
                val averageUnitPrice = if (totalQuantity > 0.0 && totalQuantity.isFinite()) {
                    validPriceRows.sumOf { it.quantity * it.unitPrice } / totalQuantity
                } else {
                    0.0
                }
                val displayReceipt = itemReceipts.minWithOrNull(
                    compareBy<ReceiptEntity> { it.item.lowercase() }.thenBy { it.item }
                ) ?: return@mapNotNull null
                val category = itemReceipts.map { it.category.trim() }
                    .filter { it.isNotBlank() }
                    .minOrNull()
                    ?: "General"

                BasketItem(
                    itemKey = key,
                    itemName = displayReceipt.item.trim(),
                    category = category,
                    brand = "",
                    totalQuantity = totalQuantity,
                    totalExpenditure = itemReceipts.sumOf { abs(it.paidTotal) },
                    averageUnitPrice = averageUnitPrice
                )
            }
    }

    /**
     * Calculates an equal-weight mean of matched normalized-item price relatives.
     * Price observations use quantity-weighted monthly unit prices, never paid_total.
     */
    fun calculateIndices(
        baseReceipts: List<ReceiptEntity>,
        currentReceipts: List<ReceiptEntity>,
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): InflationIndexResult {
        val base = consumptionReceipts(baseReceipts)
        val current = consumptionReceipts(currentReceipts)
        val currency = sharedCurrency(base, current)
        val baseBasket = aggregateReceiptsToBasketItems(base)
        val currentBasket = aggregateReceiptsToBasketItems(current)
        val basePrices = baseBasket.filter { it.averageUnitPrice.isFinite() && it.averageUnitPrice > 0.0 }
            .associateBy { it.itemKey }
        val currentPrices = currentBasket.filter { it.averageUnitPrice.isFinite() && it.averageUnitPrice > 0.0 }
            .associateBy { it.itemKey }
        val matchedKeys = basePrices.keys.intersect(currentPrices.keys).sorted()
        val itemDetails = matchedKeys.map { key ->
            val baseItem = basePrices.getValue(key)
            val currentItem = currentPrices.getValue(key)
            ItemIndexDetail(
                itemKey = key,
                itemName = baseItem.itemName,
                category = baseItem.category,
                basePrice = baseItem.averageUnitPrice,
                baseQuantity = baseItem.totalQuantity,
                baseExpenditure = baseItem.totalExpenditure,
                currentPrice = currentItem.averageUnitPrice,
                currentQuantity = currentItem.totalQuantity,
                currentExpenditure = currentItem.totalExpenditure,
                priceRatio = currentItem.averageUnitPrice / baseItem.averageUnitPrice,
                priceChangePercentage =
                    (currentItem.averageUnitPrice / baseItem.averageUnitPrice - 1.0) * 100.0
            )
        }

        val meanPriceRelative = itemDetails.takeIf { it.isNotEmpty() }?.let { details ->
            details.sumOf { it.priceRatio / details.size }
        }
        val rawPriceIndex = meanPriceRelative?.times(100.0)
        val priceStatus = when {
            (base.isNotEmpty() || current.isNotEmpty()) && currency == null ->
                IndexStatus.CURRENCY_MISMATCH
            base.isEmpty() || current.isEmpty() -> IndexStatus.INSUFFICIENT_HISTORY
            basePrices.isEmpty() -> IndexStatus.INVALID_DENOMINATOR
            matchedKeys.isEmpty() -> IndexStatus.NO_MATCHES
            itemDetails.any { !it.priceRatio.isFinite() } ||
                rawPriceIndex?.isFinite() == false -> IndexStatus.INVALID_DENOMINATOR
            else -> IndexStatus.AVAILABLE
        }
        val priceIndex = if (priceStatus == IndexStatus.AVAILABLE && rawPriceIndex != null) {
            roundTo(rawPriceIndex, 6)
        } else {
            null
        }
        val priceChange = priceIndex?.let { roundTo(it - 100.0, 6) }

        val baseExpenditure = base.sumOf { abs(it.paidTotal) }
        val currentExpenditure = current.sumOf { abs(it.paidTotal) }
        val rawExpenditureIndex = 100.0 * currentExpenditure / baseExpenditure
        val expenditureStatus = when {
            (base.isNotEmpty() || current.isNotEmpty()) && currency == null ->
                IndexStatus.CURRENCY_MISMATCH
            base.isEmpty() || current.isEmpty() -> IndexStatus.INSUFFICIENT_HISTORY
            !baseExpenditure.isFinite() || baseExpenditure <= 0.0 ||
                !currentExpenditure.isFinite() || !rawExpenditureIndex.isFinite() ->
                IndexStatus.INVALID_DENOMINATOR
            else -> IndexStatus.AVAILABLE
        }
        val expenditureIndex = if (expenditureStatus == IndexStatus.AVAILABLE) {
            roundTo(rawExpenditureIndex, 6)
        } else {
            null
        }

        return InflationIndexResult(
            basePeriod = basePeriod,
            currentPeriod = currentPeriod,
            priceIndex = priceIndex,
            priceChangePercentage = priceChange,
            expenditureIndex = expenditureIndex,
            expenditureChangePercentage = expenditureIndex?.let { roundTo(it - 100.0, 6) },
            expenditure = currentExpenditure.takeIf { it.isFinite() }?.let { roundTo(it, 6) },
            status = priceStatus,
            expenditureStatus = expenditureStatus,
            matchedItemCount = matchedKeys.size,
            baseItemCount = basePrices.size,
            currentItemCount = currentPrices.size,
            coveragePercent = if (basePrices.isNotEmpty()) {
                roundTo(100.0 * matchedKeys.size / basePrices.size, 2)
            } else {
                0.0
            },
            currency = currency,
            itemDetails = itemDetails
        )
    }

    fun isConsumption(receipt: ReceiptEntity): Boolean =
        receipt.eventType.trim().lowercase() in consumptionTypes

    private fun consumptionReceipts(receipts: List<ReceiptEntity>) =
        receipts.filter(::isConsumption)

    private fun sharedCurrency(
        base: List<ReceiptEntity>,
        current: List<ReceiptEntity>
    ): String? {
        val currencies = (base + current)
            .map { it.currency.trim().uppercase() }
            .toSet()
        return currencies.singleOrNull()?.takeIf { it.isNotBlank() }
    }

    private fun normalizeItem(item: String) = item.trim().lowercase()

    private fun roundTo(value: Double, places: Int): Double {
        var multiplier = 1.0
        repeat(places) { multiplier *= 10.0 }
        val scaled = value * multiplier
        return if (scaled.isFinite()) round(scaled) / multiplier else value
    }
}
