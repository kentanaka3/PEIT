package init.peit.domain.model

import android.graphics.Bitmap
import android.graphics.Rect
import java.util.UUID

data class ParsedReceiptItem(
    val id: String = UUID.randomUUID().toString(),
    val itemName: String = "",
    val quantity: Double = 1.0,
    val unitPrice: Double = 0.0,
    val linePrice: Double = 0.0,
    val packSize: String = "1",
    val unit: String = "piece",
    val category: String = "General",
    val brand: String = "",
    val storeTier: String = "C",
    val brandTier: String = "C",
    val productTier: String = "C",
    val storeRating: Double = 3.0,
    val brandRating: Double = 3.0,
    val productRating: Double = 3.0,
    val attributesNeedReview: Boolean = true,
    val boundingBox: Rect? = null,
    val croppedSnippetBitmap: Bitmap? = null
)

data class ParsedReceipt(
    val merchant: String = "",
    val date: String = "",
    val currency: String = "USD", // "MXN", "USD", "EUR"
    val items: List<ParsedReceiptItem> = emptyList(),
    val subtotal: Double = 0.0,
    val tax: Double = 0.0,
    val discount: Double = 0.0,
    val fee: Double = 0.0,
    val deposit: Double = 0.0,
    val paidTotal: Double = 0.0,
    val storeTier: String = "C",
    val storeRating: Double = 3.0,
    val storeAttributesNeedReview: Boolean = true,
    val confidence: Float = 1.0f,
    val rawText: String = ""
)
