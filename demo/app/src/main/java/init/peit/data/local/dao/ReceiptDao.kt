package init.peit.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import init.peit.data.local.entity.ReceiptEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ReceiptDao {

    @Query("SELECT * FROM receipts ORDER BY receipt_date DESC")
    fun getAllReceipts(): Flow<List<ReceiptEntity>>

    @Query("SELECT * FROM receipts WHERE receipt_id = :receiptId LIMIT 1")
    fun getReceiptById(receiptId: String): Flow<ReceiptEntity?>

    @Query("SELECT * FROM receipts WHERE receipt_id = :receiptId LIMIT 1")
    suspend fun getReceiptByIdSync(receiptId: String): ReceiptEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertReceipt(receipt: ReceiptEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertReceipts(receipts: List<ReceiptEntity>)

    @Update
    suspend fun updateReceipt(receipt: ReceiptEntity)

    @Delete
    suspend fun deleteReceipt(receipt: ReceiptEntity)

    @Query("SELECT * FROM receipts WHERE receipt_date >= :startDate AND receipt_date <= :endDate ORDER BY receipt_date ASC")
    fun getReceiptsBetweenDates(startDate: String, endDate: String): Flow<List<ReceiptEntity>>

    @Query("SELECT * FROM receipts WHERE receipt_date >= :startDate AND receipt_date <= :endDate ORDER BY receipt_date ASC")
    suspend fun getReceiptsBetweenDatesSync(startDate: String, endDate: String): List<ReceiptEntity>

    @Query("DELETE FROM receipts WHERE receipt_id = :receiptId")
    suspend fun deleteReceiptById(receiptId: String)

    @Query("DELETE FROM receipts")
    suspend fun deleteAllReceipts()
}
