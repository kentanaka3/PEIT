package init.peit

import init.peit.data.local.dao.LedgerDao
import init.peit.data.local.dao.ReceiptDao
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.EconometricRepositoryImpl
import init.peit.data.repository.ReceiptRepositoryImpl
import init.peit.domain.model.IndexStatus
import init.peit.domain.model.TimePeriod
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class EconometricRepositoryTest {

    private class FakeReceiptDao : ReceiptDao {
        private val receipts = MutableStateFlow<Map<String, ReceiptEntity>>(emptyMap())

        override fun getAllReceipts(): Flow<List<ReceiptEntity>> =
            receipts.map { it.values.toList() }

        override fun getReceiptsBetweenDates(
            startDate: String,
            endDate: String
        ): Flow<List<ReceiptEntity>> =
            receipts.map { map ->
                map.values.filter { it.receiptDate >= startDate && it.receiptDate <= endDate }
            }

        override suspend fun getReceiptsBetweenDatesSync(
            startDate: String,
            endDate: String
        ): List<ReceiptEntity> =
            receipts.value.values.filter { it.receiptDate >= startDate && it.receiptDate <= endDate }

        override fun getReceiptById(receiptId: String): Flow<ReceiptEntity?> =
            receipts.map { it[receiptId] }

        override suspend fun getReceiptByIdSync(receiptId: String): ReceiptEntity? =
            receipts.value[receiptId]

        override suspend fun insertReceipt(receipt: ReceiptEntity) {
            receipts.value = receipts.value + (receipt.receiptId to receipt)
        }

        override suspend fun insertReceipts(receipts: List<ReceiptEntity>) {
            this.receipts.value = this.receipts.value + receipts.associateBy { it.receiptId }
        }

        override suspend fun updateReceipt(receipt: ReceiptEntity) {
            receipts.value = receipts.value + (receipt.receiptId to receipt)
        }

        override suspend fun deleteReceipt(receipt: ReceiptEntity) {
            receipts.value = receipts.value - receipt.receiptId
        }

        override suspend fun deleteReceiptById(receiptId: String) {
            receipts.value = receipts.value - receiptId
        }

        override suspend fun deleteAllReceipts() {
            receipts.value = emptyMap()
        }
    }

    private class FakeLedgerDao : LedgerDao {
        private val entries = MutableStateFlow<Map<String, LedgerEntity>>(emptyMap())

        override fun getAllLedgerEntries(): Flow<List<LedgerEntity>> =
            entries.map { it.values.toList() }

        override fun getLedgerEntryById(entryId: String): Flow<LedgerEntity?> =
            entries.map { it[entryId] }

        override suspend fun getLedgerEntryByIdSync(entryId: String): LedgerEntity? =
            entries.value[entryId]

        override fun getLedgerEntriesByReceiptId(receiptId: String): Flow<List<LedgerEntity>> =
            entries.map { values -> values.values.filter { it.receiptId == receiptId } }

        override suspend fun getLatestLedgerEntry(): LedgerEntity? =
            entries.value.values.maxByOrNull { it.timestamp }

        override suspend fun insertLedgerEntry(entry: LedgerEntity) {
            entries.value = entries.value + (entry.entryId to entry)
        }

        override suspend fun insertLedgerEntries(entries: List<LedgerEntity>) {
            this.entries.value = this.entries.value + entries.associateBy { it.entryId }
        }

        override suspend fun updateLedgerEntry(entry: LedgerEntity) {
            entries.value = entries.value + (entry.entryId to entry)
        }

        override suspend fun deleteLedgerEntry(entry: LedgerEntity) {
            entries.value = entries.value - entry.entryId
        }

        override suspend fun deleteAllLedgerEntries() {
            entries.value = emptyMap()
        }
    }

    private suspend fun repositories(): Pair<ReceiptRepositoryImpl, EconometricRepositoryImpl> {
        val receipts = ReceiptRepositoryImpl(FakeReceiptDao(), FakeLedgerDao())
        return receipts to EconometricRepositoryImpl(receipts)
    }

    @Test
    fun calculationUsesConfirmedConsumptionAndSeparatesPriceFromExpenditure() = runTest {
        val (receipts, repository) = repositories()
        val base = TimePeriod.ofMonth("2026-01")
        val current = TimePeriod.ofMonth("2026-02")

        // A raw receipt without a valid ledger record is not a confirmed observation.
        receipts.insertReceipt(
            receipt("unconfirmed", "Coffee", "2026-01-10", 10.0, 10.0)
        )
        receipts.addReceiptWithLedger(receipt("base", "Coffee", "2026-01-11", 10.0, 10.0))
        receipts.addReceiptWithLedger(receipt("current", "Coffee", "2026-02-11", 12.0, 30.0))

        val result = repository.calculateInflationIndices(base, current)

        assertEquals(1, result.matchedItemCount)
        assertEquals(100.0, result.coveragePercent, 0.0)
        assertEquals(120.0, result.priceIndex!!, 0.0)
        assertEquals(20.0, result.priceChangePercentage!!, 0.0)
        assertEquals(300.0, result.expenditureIndex!!, 0.0)
        assertEquals(1, result.baseItemCount)
    }

    @Test
    fun flowRefreshesAfterLedgerConfirmsNewReceiptAndExcludesUnconfirmedRows() = runTest {
        val (receipts, repository) = repositories()
        val base = TimePeriod.ofMonth("2026-01")
        val current = TimePeriod.ofMonth("2026-02")
        val flow = repository.getIndexResultsFlow(base, current)

        receipts.insertReceipt(receipt("base", "Rice", "2026-01-10", 2.0, 10.0))
        receipts.insertReceipt(receipt("current", "Rice", "2026-02-10", 2.5, 10.0))
        val unconfirmed = flow.first()
        assertEquals(IndexStatus.INSUFFICIENT_HISTORY, unconfirmed.overall.status)
        assertNull(unconfirmed.overall.priceIndex)

        receipts.addReceiptWithLedger(receipt("base", "Rice", "2026-01-10", 2.0, 10.0))
        receipts.addReceiptWithLedger(receipt("current", "Rice", "2026-02-10", 2.5, 10.0))
        val confirmed = flow.first()

        assertEquals(IndexStatus.AVAILABLE, confirmed.overall.status)
        assertEquals(125.0, confirmed.overall.priceIndex!!, 0.0)
        assertEquals(1, confirmed.overall.matchedItemCount)
        assertEquals(125.0, confirmed.categories.getValue("General").priceIndex!!, 0.0)
    }

    @Test
    fun categoriesAndPeriodComparisonsUseMatchedItemResults() = runTest {
        val (receipts, repository) = repositories()
        receipts.addReceiptWithLedger(
            receipt("base-a", "Apple", "2026-01-05", 2.0, 4.0, "Food")
        )
        receipts.addReceiptWithLedger(
            receipt("base-e", "Electricity", "2026-01-10", 0.5, 50.0, "Utilities")
        )
        receipts.addReceiptWithLedger(
            receipt("current-a", "Apple", "2026-02-05", 2.5, 5.0, "Food")
        )
        receipts.addReceiptWithLedger(
            receipt("current-e", "Electricity", "2026-02-10", 0.55, 55.0, "Utilities")
        )

        val base = TimePeriod.ofMonth("2026-01")
        val feb = TimePeriod.ofMonth("2026-02")
        val categories = repository.calculateCategoryInflationIndices(base, feb)

        assertEquals(listOf("Food", "Utilities"), categories.keys.toList())
        assertEquals(125.0, categories.getValue("Food").priceIndex!!, 0.0)
        assertEquals(110.0, categories.getValue("Utilities").priceIndex!!, 0.0)

        val timeSeries = repository.calculateIndexChangesOverTime(base, listOf(feb))
        // Equal-weight matched-item relatives: 100 * ((2.5/2.0 + 0.55/0.5) / 2) = 117.5.
        assertEquals(117.5, timeSeries.single().priceIndex!!, 0.0)
    }

    private fun receipt(
        id: String,
        item: String,
        date: String,
        unitPrice: Double,
        paidTotal: Double,
        category: String = "General"
    ) = ReceiptEntity(
        receiptId = id,
        item = item,
        category = category,
        quantity = 1.0,
        unitPrice = unitPrice,
        paidTotal = paidTotal,
        currency = "USD",
        eventType = "recurring",
        receiptDate = date
    )
}
