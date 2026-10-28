package init.peit.data.repository

import init.peit.data.local.entity.ReceiptEntity
import init.peit.domain.engine.EconometricEngine
import init.peit.domain.model.InflationIndexResult
import init.peit.domain.model.TimePeriod
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

class EconometricRepositoryImpl(
    private val receiptRepository: ReceiptRepository
) : EconometricRepository {

    override suspend fun calculateInflationIndices(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): InflationIndexResult {
        val confirmed = confirmedReceipts()
        return calculate(confirmed, basePeriod, currentPeriod)
    }

    override fun getInflationIndicesFlow(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Flow<InflationIndexResult> =
        confirmedReceiptsFlow().map { calculate(it, basePeriod, currentPeriod) }

    override fun getIndexResultsFlow(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Flow<EconometricIndexSet> =
        confirmedReceiptsFlow().map { confirmed ->
            EconometricIndexSet(
                overall = calculate(confirmed, basePeriod, currentPeriod),
                categories = calculateCategories(confirmed, basePeriod, currentPeriod)
            )
        }

    override fun getCategoryInflationIndicesFlow(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Flow<Map<String, InflationIndexResult>> =
        confirmedReceiptsFlow().map { calculateCategories(it, basePeriod, currentPeriod) }

    override suspend fun calculateCategoryInflationIndices(
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Map<String, InflationIndexResult> =
        calculateCategories(confirmedReceipts(), basePeriod, currentPeriod)

    override suspend fun calculateIndexChangesOverTime(
        basePeriod: TimePeriod,
        periods: List<TimePeriod>
    ): List<InflationIndexResult> {
        val confirmed = confirmedReceipts()
        return periods.map { calculate(confirmed, basePeriod, it) }
    }

    override suspend fun calculatePeriodOverPeriodChanges(
        periods: List<TimePeriod>
    ): List<InflationIndexResult> {
        if (periods.size < 2) return emptyList()
        val confirmed = confirmedReceipts()
        return periods.zipWithNext { base, current -> calculate(confirmed, base, current) }
    }

    private suspend fun confirmedReceipts(): List<ReceiptEntity> {
        val receiptRows = receiptRepository.getAllReceipts().first()
        val validReceiptIds = receiptRepository.getAllLedgerEntries().first()
            .asSequence()
            .filter { it.isValid }
            .map { it.receiptId }
            .toSet()
        return receiptRows.filter { it.receiptId in validReceiptIds }
    }

    private fun confirmedReceiptsFlow(): Flow<List<ReceiptEntity>> =
        combine(
            receiptRepository.getAllReceipts(),
            receiptRepository.getAllLedgerEntries()
        ) { receiptRows, ledgerEntries ->
            val validReceiptIds = ledgerEntries.asSequence()
                .filter { it.isValid }
                .map { it.receiptId }
                .toSet()
            receiptRows.filter { it.receiptId in validReceiptIds }
        }

    private fun calculate(
        confirmedReceipts: List<ReceiptEntity>,
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): InflationIndexResult =
        EconometricEngine.calculateIndices(
            baseReceipts = confirmedReceipts.filter { basePeriod.contains(it.receiptDate) },
            currentReceipts = confirmedReceipts.filter { currentPeriod.contains(it.receiptDate) },
            basePeriod = basePeriod,
            currentPeriod = currentPeriod
        )

    private fun calculateCategories(
        confirmedReceipts: List<ReceiptEntity>,
        basePeriod: TimePeriod,
        currentPeriod: TimePeriod
    ): Map<String, InflationIndexResult> {
        val baseRows = confirmedReceipts.filter { basePeriod.contains(it.receiptDate) }
        val currentRows = confirmedReceipts.filter { currentPeriod.contains(it.receiptDate) }
        val categories = (baseRows + currentRows)
            .asSequence()
            .filter(EconometricEngine::isConsumption)
            .map { it.category.trim().ifBlank { "General" } }
            .toSortedSet()

        return categories.associateWith { category ->
            EconometricEngine.calculateIndices(
                baseReceipts = baseRows.filter { it.category.trim().ifBlank { "General" } == category },
                currentReceipts = currentRows.filter { it.category.trim().ifBlank { "General" } == category },
                basePeriod = basePeriod,
                currentPeriod = currentPeriod
            )
        }
    }
}
