package init.peit.domain.model

data class InflationIndexResult(
    val basePeriod: TimePeriod,
    val currentPeriod: TimePeriod,
    val priceIndex: Double?,
    val priceChangePercentage: Double?,
    val expenditureIndex: Double?,
    val expenditureChangePercentage: Double?,
    val expenditure: Double?,
    val status: IndexStatus,
    val expenditureStatus: IndexStatus,
    val matchedItemCount: Int,
    val baseItemCount: Int,
    val currentItemCount: Int,
    val coveragePercent: Double,
    val currency: String?,
    val itemDetails: List<ItemIndexDetail> = emptyList()
)

enum class IndexStatus(val message: String) {
    AVAILABLE("Available"),
    INSUFFICIENT_HISTORY("Insufficient confirmed consumption history"),
    NO_MATCHES("No matched items with valid positive prices"),
    INVALID_DENOMINATOR("No valid positive denominator"),
    CURRENCY_MISMATCH("Currencies differ; values were not converted")
}
