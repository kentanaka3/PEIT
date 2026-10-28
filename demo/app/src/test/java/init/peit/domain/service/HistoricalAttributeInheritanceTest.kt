package init.peit.domain.service

import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.repository.ReceiptRepository
import init.peit.domain.model.ParsedReceipt
import init.peit.domain.model.ParsedReceiptItem
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class HistoricalAttributeInheritanceTest {

    private lateinit var fakeRepository: FakeReceiptRepository
    private lateinit var inheritanceService: HistoricalAttributeInheritanceService

    @Before
    fun setUp() {
        fakeRepository = FakeReceiptRepository()
        inheritanceService = HistoricalAttributeInheritanceService(fakeRepository)
    }

    @Test
    fun testInheritStoreAndItemAttributesFromHistory() = runTest {
        // Seed historical receipts
        fakeRepository.receiptsList.add(
            ReceiptEntity(
                receiptId = "1",
                merchant = "Walmart",
                item = "Leche Lala 1L",
                category = "Dairy",
                brand = "Lala",
                storeTier = "Tier 1 Supermarket",
                brandTier = "Premium Brand",
                packSize = "1L",
                unit = "L"
            )
        )

        val newReceipt = ParsedReceipt(
            merchant = "Walmart",
            date = "2026-10-22",
            items = listOf(
                ParsedReceiptItem(
                    itemName = "Leche Lala 1L",
                    quantity = 2.0,
                    unitPrice = 28.50,
                    linePrice = 57.00
                )
            )
        )

        val inherited = inheritanceService.inheritAttributes(newReceipt)

        assertEquals("Tier 1 Supermarket", inherited.storeTier)
        val inheritedItem = inherited.items.first()
        assertEquals("Dairy", inheritedItem.category)
        assertEquals("Lala", inheritedItem.brand)
        assertEquals("Premium Brand", inheritedItem.brandTier)
        assertEquals("1L", inheritedItem.packSize)
        assertEquals("L", inheritedItem.unit)
    }

    @Test
    fun historyReadFailureIsNotSilentlyIgnored() = runTest {
        fakeRepository.historyError = IllegalStateException("history unavailable")
        val error = runCatching {
            inheritanceService.inheritAttributes(ParsedReceipt(merchant = "Walmart"))
        }.exceptionOrNull()
        assertTrue(error is IllegalStateException)
        assertEquals("history unavailable", error?.message)
    }

    @Test
    fun historyReadCancellationPropagates() = runTest {
        fakeRepository.historyError = CancellationException("cancelled")
        val error = runCatching {
            inheritanceService.inheritAttributes(ParsedReceipt(merchant = "Walmart"))
        }.exceptionOrNull()
        assertTrue(error is CancellationException)
    }

    private class FakeReceiptRepository : ReceiptRepository {
        val receiptsList = mutableListOf<ReceiptEntity>()
        var historyError: Exception? = null

        override fun getAllReceipts(): Flow<List<ReceiptEntity>> =
            historyError?.let { error -> flow { throw error } } ?: flowOf(receiptsList)
        override fun getReceiptsBetweenDates(startDate: String, endDate: String): Flow<List<ReceiptEntity>> = flowOf(receiptsList)
        override suspend fun getReceiptsBetweenDatesSync(startDate: String, endDate: String): List<ReceiptEntity> = receiptsList
        override fun getReceiptById(receiptId: String): Flow<ReceiptEntity?> = flowOf(receiptsList.find { it.receiptId == receiptId })
        override suspend fun getReceiptByIdSync(receiptId: String): ReceiptEntity? = receiptsList.find { it.receiptId == receiptId }
        override suspend fun insertReceipt(receipt: ReceiptEntity) { receiptsList.add(receipt) }
        override suspend fun insertReceipts(receipts: List<ReceiptEntity>) { receiptsList.addAll(receipts) }
        override suspend fun updateReceipt(receipt: ReceiptEntity) {}
        override suspend fun deleteReceipt(receipt: ReceiptEntity) {}
        override suspend fun deleteReceiptById(receiptId: String) {}
        override suspend fun deleteAllReceipts() { receiptsList.clear() }
        override fun getAllLedgerEntries(): Flow<List<init.peit.data.local.entity.LedgerEntity>> = flowOf(emptyList())
        override fun getLedgerEntryById(entryId: String): Flow<init.peit.data.local.entity.LedgerEntity?> = flowOf(null)
        override fun getLedgerEntriesByReceiptId(receiptId: String): Flow<List<init.peit.data.local.entity.LedgerEntity>> = flowOf(emptyList())
        override suspend fun getLedgerEntryByIdSync(entryId: String): init.peit.data.local.entity.LedgerEntity? = null
        override suspend fun insertLedgerEntry(entry: init.peit.data.local.entity.LedgerEntity) {}
        override suspend fun addReceiptWithLedger(receipt: ReceiptEntity): LedgerEntity =
            addReceiptsWithLedger(listOf(receipt)).single()
        override suspend fun addReceiptsWithLedger(receipts: List<ReceiptEntity>): List<LedgerEntity> {
            receiptsList.addAll(receipts)
            return receipts.map { receipt ->
                LedgerEntity(
                    entryId = "ledger_${receipt.receiptId}",
                    receiptId = receipt.receiptId,
                    item = receipt.item,
                    paidTotal = receipt.paidTotal,
                    receiptDate = receipt.receiptDate
                )
            }
        }
        override suspend fun verifyLedgerIntegrity(): Boolean = true
    }
}
