package init.peit.domain.model

data class ItemIndexDetail(
    val itemKey: String,
    val itemName: String,
    val category: String,
    val basePrice: Double,
    val baseQuantity: Double,
    val baseExpenditure: Double,
    val currentPrice: Double,
    val currentQuantity: Double,
    val currentExpenditure: Double,
    val priceRatio: Double,
    val priceChangePercentage: Double
)
