package init.peit.data.repository

import init.peit.domain.model.InflationIndexResult
import init.peit.domain.model.TimePeriod
import kotlinx.coroutines.flow.Flow

data class EconometricIndexSet(
    val overall: InflationIndexResult,
    val categories: Map<String, InflationIndexResult>
)

interface EconometricRepository {

    /**
     * Emits overall and category results calculated from one repository snapshot.
     */
    fun getIndexResultsFlow(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Flow<EconometricIndexSet>

    /**
     * Calculates matched-item price relatives and a separate expenditure comparison.
     */
    suspend fun calculateInflationIndices(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): InflationIndexResult

    /**
     * Emits updated indices whenever confirmed receipts or ledger validity changes.
     */
    fun getInflationIndicesFlow(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Flow<InflationIndexResult>

    /**
     * Reactive category-level matched-item price relatives and expenditure comparisons.
     */
    fun getCategoryInflationIndicesFlow(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Flow<Map<String, InflationIndexResult>>

    /**
     * Calculates matched-item price relatives and expenditure comparisons by category.
     */
    suspend fun calculateCategoryInflationIndices(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Map<String, InflationIndexResult>

    /**
     * Calculates matched-item price relatives for periods relative to a fixed basePeriod.
     */
    suspend fun calculateIndexChangesOverTime(
        basePeriod: TimePeriod,
        periods: List<TimePeriod>
    ): List<InflationIndexResult>

    /**
     * Calculates period-over-period matched-item price relatives.
     */
    suspend fun calculatePeriodOverPeriodChanges(
        periods: List<TimePeriod>
    ): List<InflationIndexResult>
}
