package init.peit.data.repository

import androidx.room.withTransaction
import init.peit.data.local.database.AppDatabase
import init.peit.data.local.dao.LedgerDao
import init.peit.data.local.dao.ReceiptDao
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.util.LedgerHasher
import init.peit.data.util.ReceiptContract
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class ReceiptRepositoryImpl private constructor(
    private val receiptDao: ReceiptDao,
    private val ledgerDao: LedgerDao,
    private val database: AppDatabase?
) : ReceiptRepository {

    constructor(database: AppDatabase) : this(
        receiptDao = database.receiptDao(),
        ledgerDao = database.ledgerDao(),
        database = database
    )

    // Fake-DAO compatibility for unit tests; production must use the AppDatabase constructor.
    constructor(receiptDao: ReceiptDao, ledgerDao: LedgerDao) : this(
        receiptDao = receiptDao,
        ledgerDao = ledgerDao,
        database = null
    )

    private val appendMutex = Mutex()

    override fun getAllReceipts(): Flow<List<ReceiptEntity>> = receiptDao.getAllReceipts()

    override fun getReceiptsBetweenDates(startDate: String, endDate: String): Flow<List<ReceiptEntity>> =
        receiptDao.getReceiptsBetweenDates(startDate, endDate)

    override suspend fun getReceiptsBetweenDatesSync(startDate: String, endDate: String): List<ReceiptEntity> =
        receiptDao.getReceiptsBetweenDatesSync(startDate, endDate)

    override fun getReceiptById(receiptId: String): Flow<ReceiptEntity?> =
        receiptDao.getReceiptById(receiptId)

    override suspend fun getReceiptByIdSync(receiptId: String): ReceiptEntity? =
        receiptDao.getReceiptByIdSync(receiptId)

    override suspend fun insertReceipt(receipt: ReceiptEntity) {
        val canonicalReceipt = ReceiptContract.canonicalize(receipt)
        requireIdentityUnchanged(canonicalReceipt)
        receiptDao.insertReceipt(canonicalReceipt)
    }

    override suspend fun insertReceipts(receipts: List<ReceiptEntity>) {
        val canonicalReceipts = receipts.map { ReceiptContract.canonicalize(it) }
        canonicalReceipts.forEach { requireIdentityUnchanged(it) }
        receiptDao.insertReceipts(canonicalReceipts)
    }

    override suspend fun updateReceipt(receipt: ReceiptEntity) {
        val canonicalReceipt = ReceiptContract.canonicalize(receipt)
        requireIdentityUnchanged(canonicalReceipt)
        receiptDao.updateReceipt(canonicalReceipt)
    }

    override suspend fun deleteReceipt(receipt: ReceiptEntity) {
        requireNotConfirmed(receipt.receiptId)
        receiptDao.deleteReceipt(receipt)
    }

    override suspend fun deleteReceiptById(receiptId: String) {
        requireNotConfirmed(receiptId)
        receiptDao.deleteReceiptById(receiptId)
    }

    override suspend fun deleteAllReceipts() {
        if (ledgerDao.getAllLedgerEntries().first().isNotEmpty()) {
            throw IllegalStateException("Receipts referenced by the confirmed ledger cannot be deleted.")
        }
        receiptDao.deleteAllReceipts()
    }

    override fun getAllLedgerEntries(): Flow<List<LedgerEntity>> = ledgerDao.getAllLedgerEntries()

    override fun getLedgerEntryById(entryId: String): Flow<LedgerEntity?> =
        ledgerDao.getLedgerEntryById(entryId)

    override fun getLedgerEntriesByReceiptId(receiptId: String): Flow<List<LedgerEntity>> =
        ledgerDao.getLedgerEntriesByReceiptId(receiptId)

    override suspend fun getLedgerEntryByIdSync(entryId: String): LedgerEntity? =
        ledgerDao.getLedgerEntryByIdSync(entryId)

    override suspend fun insertLedgerEntry(entry: LedgerEntity) {
        ledgerDao.insertLedgerEntry(entry)
    }

    override suspend fun addReceiptWithLedger(receipt: ReceiptEntity): LedgerEntity =
        addReceiptsWithLedger(listOf(receipt)).single()

    override suspend fun addReceiptsWithLedger(receipts: List<ReceiptEntity>): List<LedgerEntity> {
        if (receipts.isEmpty()) return emptyList()
        val canonicalReceipts = receipts.map { ReceiptContract.canonicalize(it) }
        require(canonicalReceipts.map { it.receiptId }.toSet().size == canonicalReceipts.size) {
            "A batch cannot contain multiple receipt rows with the same receipt ID."
        }

        return appendMutex.withLock {
            val append: suspend () -> List<LedgerEntity> = {
                val existingEntries = ledgerDao.getAllLedgerEntries().first()
                var chainTip = LedgerHasher.orderedChain(existingEntries)?.lastOrNull()?.entryId
                    ?: if (existingEntries.isEmpty()) null
                    else throw IllegalStateException("Ledger predecessor chain is inconsistent.")
                val entriesById = existingEntries.associateBy { it.entryId }
                existingEntries.forEach { entry ->
                    val storedReceipt = receiptDao.getReceiptByIdSync(entry.receiptId)
                        ?: throw IllegalStateException("Ledger entry has no stored receipt.")
                    if (!LedgerHasher.verifyIntegrity(entry, storedReceipt)) {
                        throw IllegalStateException("Existing ledger identity does not match its receipt.")
                    }
                }

                canonicalReceipts.forEach { receipt ->
                    val linkedEntries = existingEntries.filter { it.receiptId == receipt.receiptId }
                    if (linkedEntries.any { !LedgerHasher.verifyIntegrity(it, receipt) }) {
                        throw IllegalArgumentException(
                            "Confirmed receipt identity fields (ID, item, paid total, and date) cannot be changed."
                        )
                    }
                }

                val additions = mutableListOf<LedgerEntity>()
                val result = canonicalReceipts.map { receipt ->
                    val entryId = LedgerHasher.computeEntryId(receipt)
                    val existing = entriesById[entryId]
                    if (existing != null) {
                        if (!LedgerHasher.verifyIntegrity(existing, receipt)) {
                            throw IllegalStateException("Ledger identity hash collision or mismatched receipt.")
                        }
                        existing
                    } else {
                        LedgerEntity(
                            entryId = entryId,
                            receiptId = receipt.receiptId,
                            item = receipt.item,
                            paidTotal = receipt.paidTotal,
                            receiptDate = receipt.receiptDate,
                            previousHash = chainTip
                        ).also { entry ->
                            additions += entry
                            chainTip = entry.entryId
                        }
                    }
                }

                receiptDao.insertReceipts(canonicalReceipts)
                if (additions.isNotEmpty()) {
                    ledgerDao.insertLedgerEntries(additions)
                }
                result
            }

            database?.withTransaction(append) ?: append()
        }
    }

    override suspend fun verifyLedgerIntegrity(): Boolean {
        val entries = ledgerDao.getAllLedgerEntries().first()
        if (LedgerHasher.orderedChain(entries) == null) return false

        for (entry in entries) {
            val receipt = receiptDao.getReceiptByIdSync(entry.receiptId) ?: return false
            if (!LedgerHasher.verifyIntegrity(entry, receipt)) return false
        }
        return true
    }

    private suspend fun requireNotConfirmed(receiptId: String) {
        if (ledgerDao.getLedgerEntriesByReceiptId(receiptId).first().isNotEmpty()) {
            throw IllegalStateException("A receipt referenced by the confirmed ledger cannot be deleted.")
        }
    }

    private suspend fun requireIdentityUnchanged(receipt: ReceiptEntity) {
        val entries = ledgerDao.getLedgerEntriesByReceiptId(receipt.receiptId).first()
        if (entries.any { !LedgerHasher.verifyIntegrity(it, receipt) }) {
            throw IllegalArgumentException(
                "Confirmed receipt identity fields (ID, item, paid total, and date) cannot be changed."
            )
        }
    }
}
