package init.peit.domain.service

import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.ReceiptRepository
import init.peit.domain.model.ParsedReceipt
import kotlinx.coroutines.flow.first
import java.util.Locale

class HistoricalAttributeInheritanceService(
    private val receiptRepository: ReceiptRepository
) {

    /**
     * Inherits attributes from past stored receipts for matching merchant and item names.
     */
    suspend fun inheritAttributes(parsedReceipt: ParsedReceipt): ParsedReceipt {
        val historicalReceipts = receiptRepository.getAllReceipts().first()

        if (historicalReceipts.isEmpty()) return parsedReceipt

        // 1. Inherit store tier & store rating for merchant
        var inheritedStoreTier = parsedReceipt.storeTier
        var inheritedStoreRating = parsedReceipt.storeRating
        val merchantMatch = findMerchantMatch(parsedReceipt.merchant, historicalReceipts)
        if (merchantMatch != null) {
            if (parsedReceipt.storeAttributesNeedReview || inheritedStoreTier.isBlank()) {
                inheritedStoreTier = merchantMatch.storeTier.takeIf { it.isNotBlank() } ?: inheritedStoreTier
            }
            if (parsedReceipt.storeAttributesNeedReview && merchantMatch.storeRating > 0.0) {
                inheritedStoreRating = merchantMatch.storeRating
            }
        }

        // 2. Inherit item attributes for each item
        val updatedItems = parsedReceipt.items.map { item ->
            val itemMatch = findItemMatch(item.itemName, historicalReceipts)
            if (itemMatch != null) {
                item.copy(
                    category = if (item.attributesNeedReview || item.category.isBlank() || item.category == "General") itemMatch.category.takeIf { it.isNotBlank() } ?: item.category else item.category,
                    brand = if (item.attributesNeedReview || item.brand.isBlank()) itemMatch.brand.takeIf { it.isNotBlank() } ?: item.brand else item.brand,
                    storeTier = if (item.attributesNeedReview || item.storeTier.isBlank()) {
                        merchantMatch?.storeTier?.takeIf { it.isNotBlank() } ?: itemMatch.storeTier.takeIf { it.isNotBlank() } ?: item.storeTier
                    } else item.storeTier,
                    brandTier = if (item.attributesNeedReview || item.brandTier.isBlank()) itemMatch.brandTier.takeIf { it.isNotBlank() } ?: item.brandTier else item.brandTier,
                    productTier = if (item.attributesNeedReview || item.productTier.isBlank()) itemMatch.productTier.takeIf { it.isNotBlank() } ?: item.productTier else item.productTier,
                    unit = if (item.attributesNeedReview || item.unit.isBlank()) itemMatch.unit.takeIf { it.isNotBlank() } ?: item.unit else item.unit,
                    packSize = if (item.attributesNeedReview || item.packSize.isBlank()) itemMatch.packSize.takeIf { it.isNotBlank() } ?: item.packSize else item.packSize,
                    storeRating = if (item.attributesNeedReview) {
                        merchantMatch?.storeRating?.takeIf { it > 0.0 } ?: itemMatch.storeRating.takeIf { it > 0.0 } ?: item.storeRating
                    } else item.storeRating,
                    brandRating = if (item.attributesNeedReview) itemMatch.brandRating.takeIf { it > 0.0 } ?: item.brandRating else item.brandRating,
                    productRating = if (item.attributesNeedReview) itemMatch.productRating.takeIf { it > 0.0 } ?: item.productRating else item.productRating,
                    attributesNeedReview = true
                )
            } else {
                item.copy(
                    storeTier = if (item.attributesNeedReview) inheritedStoreTier else item.storeTier,
                    storeRating = if (item.attributesNeedReview) inheritedStoreRating else item.storeRating
                )
            }
        }

        return parsedReceipt.copy(
            storeTier = inheritedStoreTier,
            storeRating = inheritedStoreRating,
            items = updatedItems
        )
    }

    private fun findMerchantMatch(
        merchantName: String,
        history: List<ReceiptEntity>
    ): ReceiptEntity? {
        if (merchantName.isBlank()) return null
        val target = merchantName.trim().lowercase(Locale.ROOT)
        return history.firstOrNull { it.merchant.trim().lowercase(Locale.ROOT) == target && it.storeTier.isNotBlank() }
            ?: history.firstOrNull { it.merchant.trim().lowercase(Locale.ROOT).contains(target) }
    }

    private fun findItemMatch(
        itemName: String,
        history: List<ReceiptEntity>
    ): ReceiptEntity? {
        if (itemName.isBlank()) return null
        val target = itemName.trim().lowercase(Locale.ROOT)

        // Exact match
        val exact = history.firstOrNull { it.item.trim().lowercase(Locale.ROOT) == target }
        if (exact != null) return exact

        // Substring match
        return history.firstOrNull {
            val histName = it.item.trim().lowercase(Locale.ROOT)
            histName.contains(target) || target.contains(histName)
        }
    }
}
