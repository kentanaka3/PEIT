package init.peit.data.ocr

import android.graphics.Bitmap
import android.graphics.Rect
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.math.max
import kotlin.math.min

class ReceiptImageCropper {

    /**
     * Crops a bounding box snippet from a receipt image off-thread,
     * applying +15% descender padding to the bottom to prevent cutting off text descenders.
     */
    suspend fun cropSnippetWithDescenderPadding(
        sourceBitmap: Bitmap,
        boundingBox: Rect?
    ): Bitmap? = withContext(Dispatchers.Default) {
        if (boundingBox == null) return@withContext null
        check(!sourceBitmap.isRecycled) { "Cannot crop a recycled receipt image" }

        val width = sourceBitmap.width
        val height = sourceBitmap.height

        if (width <= 0 || height <= 0) return@withContext null

        val boundingBoxHeight = boundingBox.bottom - boundingBox.top
        val descenderPadding = (boundingBoxHeight * 0.15f).toInt()

        val left = max(0, boundingBox.left)
        val top = max(0, boundingBox.top)
        val right = min(width, boundingBox.right)
        val bottom = min(height, boundingBox.bottom + descenderPadding)

        val cropWidth = right - left
        val cropHeight = bottom - top

        if (cropWidth <= 0 || cropHeight <= 0) return@withContext null

        val snippet = Bitmap.createBitmap(sourceBitmap, left, top, cropWidth, cropHeight)
        if (snippet === sourceBitmap) {
            snippet.copy(Bitmap.Config.ARGB_8888, false)
                ?: throw IllegalStateException("Could not copy receipt image snippet")
        } else {
            snippet
        }
    }
}
