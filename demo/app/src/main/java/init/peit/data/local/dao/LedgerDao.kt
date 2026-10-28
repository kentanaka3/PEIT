package init.peit.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import init.peit.data.local.entity.LedgerEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface LedgerDao {

    @Query("SELECT * FROM ledger_entries ORDER BY timestamp DESC")
    fun getAllLedgerEntries(): Flow<List<LedgerEntity>>

    @Query("SELECT * FROM ledger_entries WHERE entry_id = :entryId LIMIT 1")
    fun getLedgerEntryById(entryId: String): Flow<LedgerEntity?>

    @Query("SELECT * FROM ledger_entries WHERE entry_id = :entryId LIMIT 1")
    suspend fun getLedgerEntryByIdSync(entryId: String): LedgerEntity?

    @Query("SELECT * FROM ledger_entries WHERE receipt_id = :receiptId")
    fun getLedgerEntriesByReceiptId(receiptId: String): Flow<List<LedgerEntity>>

    @Query("SELECT * FROM ledger_entries ORDER BY timestamp DESC LIMIT 1")
    suspend fun getLatestLedgerEntry(): LedgerEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLedgerEntry(entry: LedgerEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLedgerEntries(entries: List<LedgerEntity>)

    @Update
    suspend fun updateLedgerEntry(entry: LedgerEntity)

    @Delete
    suspend fun deleteLedgerEntry(entry: LedgerEntity)

    @Query("DELETE FROM ledger_entries")
    suspend fun deleteAllLedgerEntries()
}
