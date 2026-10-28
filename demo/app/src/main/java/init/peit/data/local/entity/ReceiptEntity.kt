package init.peit.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import java.util.UUID

@Entity(tableName = "receipts")
data class ReceiptEntity(
    @PrimaryKey
    @ColumnInfo(name = "receipt_id")
    val receiptId: String = UUID.randomUUID().toString(),

    @ColumnInfo(name = "receipt_date")
    val receiptDate: String = "",

    @ColumnInfo(name = "merchant")
    val merchant: String = "",

    @ColumnInfo(name = "item")
    val item: String = "",

    @ColumnInfo(name = "brand")
    val brand: String = "",

    @ColumnInfo(name = "category")
    val category: String = "",

    @ColumnInfo(name = "quantity")
    val quantity: Double = 1.0,

    @ColumnInfo(name = "pack_size")
    val packSize: String = "1",

    @ColumnInfo(name = "unit")
    val unit: String = "piece",

    @ColumnInfo(name = "unit_price")
    val unitPrice: Double = 0.0,

    @ColumnInfo(name = "currency")
    val currency: String = "USD",

    @ColumnInfo(name = "discount")
    val discount: Double = 0.0,

    @ColumnInfo(name = "fee")
    val fee: Double = 0.0,

    @ColumnInfo(name = "tax")
    val tax: Double = 0.0,

    @ColumnInfo(name = "deposit")
    val deposit: Double = 0.0,

    @ColumnInfo(name = "paid_total")
    val paidTotal: Double = 0.0,

    @ColumnInfo(name = "event_type")
    val eventType: String = "one_off",

    // Provisional analyst defaults only; these tiers and ratings are not observations.
    @ColumnInfo(name = "store_tier")
    val storeTier: String = "C",

    @ColumnInfo(name = "store_rating")
    val storeRating: Double = 3.0,

    @ColumnInfo(name = "brand_tier")
    val brandTier: String = "C",

    @ColumnInfo(name = "brand_rating")
    val brandRating: Double = 3.0,

    @ColumnInfo(name = "product_tier")
    val productTier: String = "C",

    @ColumnInfo(name = "product_rating")
    val productRating: Double = 3.0,

    @ColumnInfo(name = "availability")
    val availability: String = "in_stock",

    @ColumnInfo(name = "notes")
    val notes: String = ""
)
