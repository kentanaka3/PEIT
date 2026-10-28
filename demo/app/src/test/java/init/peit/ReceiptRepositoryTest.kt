package init.peit

import init.peit.data.local.dao.LedgerDao
import init.peit.data.local.dao.ReceiptDao
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.local.database.DatabaseSeeder
import init.peit.data.repository.ReceiptRepositoryImpl
import init.peit.data.util.LedgerHasher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReceiptRepositoryTest {

    private class FakeReceiptDao : ReceiptDao {
        private val receipts = MutableStateFlow<Map<String, ReceiptEntity>>(emptyMap())

        override fun getAllReceipts(): Flow<List<ReceiptEntity>> =
            receipts.map { it.values.toList() }

        override fun getReceiptsBetweenDates(startDate: String, endDate: String): Flow<List<ReceiptEntity>> =
            receipts.map { map -> map.values.filter { it.receiptDate in startDate..endDate } }

        override suspend fun getReceiptsBetweenDatesSync(startDate: String, endDate: String): List<ReceiptEntity> =
            receipts.value.values.filter { it.receiptDate in startDate..endDate }

        override fun getReceiptById(receiptId: String): Flow<ReceiptEntity?> =
            receipts.map { it[receiptId] }

        override suspend fun getReceiptByIdSync(receiptId: String): ReceiptEntity? = receipts.value[receiptId]

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
        private val ledgerEntries = MutableStateFlow<Map<String, LedgerEntity>>(emptyMap())

        override fun getAllLedgerEntries(): Flow<List<LedgerEntity>> =
            ledgerEntries.map { it.values.toList() }

        override fun getLedgerEntryById(entryId: String): Flow<LedgerEntity?> =
            ledgerEntries.map { it[entryId] }

        override suspend fun getLedgerEntryByIdSync(entryId: String): LedgerEntity? =
            ledgerEntries.value[entryId]

        override fun getLedgerEntriesByReceiptId(receiptId: String): Flow<List<LedgerEntity>> =
            ledgerEntries.map { map -> map.values.filter { it.receiptId == receiptId } }

        override suspend fun getLatestLedgerEntry(): LedgerEntity? =
            ledgerEntries.value.values.maxByOrNull { it.timestamp }

        override suspend fun insertLedgerEntry(entry: LedgerEntity) {
            ledgerEntries.value = ledgerEntries.value + (entry.entryId to entry)
        }

        override suspend fun insertLedgerEntries(entries: List<LedgerEntity>) {
            ledgerEntries.value = ledgerEntries.value + entries.associateBy { it.entryId }
        }

        override suspend fun updateLedgerEntry(entry: LedgerEntity) {
            ledgerEntries.value = ledgerEntries.value + (entry.entryId to entry)
        }

        override suspend fun deleteLedgerEntry(entry: LedgerEntity) {
            ledgerEntries.value = ledgerEntries.value - entry.entryId
        }

        override suspend fun deleteAllLedgerEntries() {
            ledgerEntries.value = emptyMap()
        }
    }

    private fun newRepository(): Triple<FakeReceiptDao, FakeLedgerDao, ReceiptRepositoryImpl> {
        val receiptDao = FakeReceiptDao()
        val ledgerDao = FakeLedgerDao()
        return Triple(receiptDao, ledgerDao, ReceiptRepositoryImpl(receiptDao, ledgerDao))
    }

    @Test
    fun addReceiptWithLedger_persistsReceiptAndCanonicalIdentity() = runTest {
        val (receiptDao, ledgerDao, repository) = newRepository()
        val receipt = receipt("REC-5001", "Coffee Beans", -14.99)

        val entry = repository.addReceiptWithLedger(receipt)

        assertEquals(LedgerHasher.computeEntryId(receipt), entry.entryId)
        assertEquals("REC-5001", entry.receiptId)
        assertNotNull(receiptDao.getReceiptByIdSync("REC-5001"))
        assertEquals(1, ledgerDao.getAllLedgerEntries().first().size)
        assertTrue(repository.verifyLedgerIntegrity())
    }

    @Test
    fun addReceiptsWithLedger_appendsBatchInOrderAndDeduplicatesRetries() = runTest {
        val (_, ledgerDao, repository) = newRepository()
        val first = receipt("REC-1", "Milk", -2.5)
        val second = receipt("REC-2", "Bread", -3.0)

        val result = repository.addReceiptsWithLedger(listOf(first, second))
        val retry = repository.addReceiptsWithLedger(listOf(first, second))

        assertEquals(2, result.size)
        assertEquals(null, result.first().previousHash)
        assertEquals(result.first().entryId, result.last().previousHash)
        assertEquals(result, retry)
        assertEquals(2, ledgerDao.getAllLedgerEntries().first().size)
        assertTrue(repository.verifyLedgerIntegrity())
    }

    @Test
    fun addReceiptsWithLedger_rejectsDuplicateReceiptIdsWithinBatch() = runTest {
        val (_, ledgerDao, repository) = newRepository()
        val first = receipt("REC-1", "Milk", -2.5)
        val conflicting = first.copy(item = "Other item")

        try {
            repository.addReceiptsWithLedger(listOf(first, conflicting))
            throw AssertionError("Expected duplicate receipt ID validation to fail")
        } catch (_: IllegalArgumentException) {
            assertTrue(ledgerDao.getAllLedgerEntries().first().isEmpty())
        }
    }

    @Test
    fun concurrentAppends_doNotForkChain() = runTest {
        val (_, ledgerDao, repository) = newRepository()
        val first = async(Dispatchers.Default) { repository.addReceiptWithLedger(receipt("REC-1", "Milk", -2.5)) }
        val second = async(Dispatchers.Default) { repository.addReceiptWithLedger(receipt("REC-2", "Bread", -3.0)) }

        first.await()
        second.await()

        assertEquals(2, ledgerDao.getAllLedgerEntries().first().size)
        assertTrue(repository.verifyLedgerIntegrity())
    }

    @Test
    fun verifyLedgerIntegrity_rejectsChainWithMissingPredecessor() = runTest {
        val (_, ledgerDao, repository) = newRepository()
        val receipt = receipt("REC-1", "Milk", -2.5)
        val first = repository.addReceiptWithLedger(receipt)
        ledgerDao.insertLedgerEntry(
            LedgerEntity(
                entryId = "orphan",
                receiptId = "REC-2",
                item = "Bread",
                paidTotal = -3.0,
                receiptDate = "2026-10-22",
                previousHash = "missing"
            )
        )

        assertFalse(repository.verifyLedgerIntegrity())
        assertNotNull(first)
    }

    @Test
    fun confirmedReceipt_allowsLabelEditsButRejectsIdentityChangesAndDeletion() = runTest {
        val (_, _, repository) = newRepository()
        val original = receipt("REC-1", "Milk", -2.5)
        repository.addReceiptWithLedger(original)

        repository.updateReceipt(original.copy(category = "Groceries", notes = "human reviewed label"))
        assertTrue(repository.verifyLedgerIntegrity())

        try {
            repository.updateReceipt(original.copy(paidTotal = -2.0))
            throw AssertionError("Expected confirmed identity mutation to fail")
        } catch (_: IllegalArgumentException) {
            assertTrue(repository.verifyLedgerIntegrity())
        }
        try {
            repository.deleteReceiptById(original.receiptId)
            throw AssertionError("Expected confirmed receipt deletion to fail")
        } catch (_: IllegalStateException) {
            assertTrue(repository.verifyLedgerIntegrity())
        }
    }

    @Test
    fun seedIfEmpty_isIdempotentAndUsesSyntheticCanonicalRows() = runTest {
        val (receiptDao, ledgerDao, repository) = newRepository()

        DatabaseSeeder.seedIfEmpty(repository)
        DatabaseSeeder.seedIfEmpty(repository)

        val seeded = receiptDao.getAllReceipts().first()
        assertEquals(10, seeded.size)
        assertTrue(seeded.all { it.paidTotal < 0.0 })
        assertTrue(seeded.all { it.packSize.toBigDecimalOrNull()?.signum() == 1 && it.unit.isNotBlank() })
        assertTrue(seeded.all { it.notes.contains("Synthetic/demo data only") })
        assertEquals(10, ledgerDao.getAllLedgerEntries().first().size)
        assertTrue(repository.verifyLedgerIntegrity())
    }

    private fun receipt(id: String, item: String, total: Double) = ReceiptEntity(
        receiptId = id,
        item = item,
        paidTotal = total,
        receiptDate = "2026-10-22"
    )
}
