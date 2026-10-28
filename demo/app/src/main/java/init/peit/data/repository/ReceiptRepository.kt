package init.peit.data.repository

import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import kotlinx.coroutines.flow.Flow

interface ReceiptRepository {
    // Receipts Flow API
    fun getAllReceipts(): Flow<List<ReceiptEntity>>
    fun getReceiptsBetweenDates(startDate: String, endDate: String): Flow<List<ReceiptEntity>>
    suspend fun getReceiptsBetweenDatesSync(startDate: String, endDate: String): List<ReceiptEntity>
    fun getReceiptById(receiptId: String): Flow<ReceiptEntity?>
    suspend fun getReceiptByIdSync(receiptId: String): ReceiptEntity?
    suspend fun insertReceipt(receipt: ReceiptEntity)
    suspend fun insertReceipts(receipts: List<ReceiptEntity>)
    suspend fun updateReceipt(receipt: ReceiptEntity)
    suspend fun deleteReceipt(receipt: ReceiptEntity)
    suspend fun deleteReceiptById(receiptId: String)
    suspend fun deleteAllReceipts()

    // Ledger Entries Flow API
    fun getAllLedgerEntries(): Flow<List<LedgerEntity>>
    fun getLedgerEntryById(entryId: String): Flow<LedgerEntity?>
    fun getLedgerEntriesByReceiptId(receiptId: String): Flow<List<LedgerEntity>>
    suspend fun getLedgerEntryByIdSync(entryId: String): LedgerEntity?
    suspend fun insertLedgerEntry(entry: LedgerEntity)

    // Transaction & Integrity API
    suspend fun addReceiptWithLedger(receipt: ReceiptEntity): LedgerEntity
    suspend fun addReceiptsWithLedger(receipts: List<ReceiptEntity>): List<LedgerEntity>
    suspend fun verifyLedgerIntegrity(): Boolean
}
