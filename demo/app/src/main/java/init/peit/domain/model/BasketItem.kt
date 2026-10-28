package init.peit.domain.model

data class BasketItem(
    val itemKey: String,
    val itemName: String,
    val category: String = "General",
    val brand: String = "",
    val totalQuantity: Double,
    val totalExpenditure: Double,
    val averageUnitPrice: Double
)
