package init.peit.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "ledger_entries")
data class LedgerEntity(
    @PrimaryKey
    @ColumnInfo(name = "entry_id")
    val entryId: String,

    @ColumnInfo(name = "receipt_id")
    val receiptId: String,

    @ColumnInfo(name = "item")
    val item: String,

    @ColumnInfo(name = "paid_total")
    val paidTotal: Double,

    @ColumnInfo(name = "receipt_date")
    val receiptDate: String,

    @ColumnInfo(name = "previous_hash")
    val previousHash: String? = null,

    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis(),

    @ColumnInfo(name = "is_valid")
    val isValid: Boolean = true
)
