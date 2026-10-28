package init.peit.data.ocr

import android.content.Context
import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.ParcelFileDescriptor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException

class PdfDocumentParser(private val context: Context) {

    suspend fun renderPdfPagesToBitmaps(uri: Uri, maxPages: Int = 10): List<Bitmap> = withContext(Dispatchers.IO) {
        require(maxPages > 0) { "Maximum PDF page count must be positive" }
        val bitmaps = mutableListOf<Bitmap>()
        var descriptor: ParcelFileDescriptor? = null
        var renderer: PdfRenderer? = null

        try {
            descriptor = if (uri.scheme == "file") {
                val path = uri.path ?: throw IOException("PDF file path is missing")
                ParcelFileDescriptor.open(File(path), ParcelFileDescriptor.MODE_READ_ONLY)
            } else {
                context.contentResolver.openFileDescriptor(uri, "r")
                    ?: throw IOException("Could not open the selected PDF")
            }
            renderer = PdfRenderer(descriptor)
            if (renderer.pageCount > maxPages) {
                throw IOException("PDF has ${renderer.pageCount} pages; the limit is $maxPages")
            }

            for (index in 0 until renderer.pageCount) {
                val page = renderer.openPage(index)
                try {
                    val bitmap = Bitmap.createBitmap(
                        page.width * 2,
                        page.height * 2,
                        Bitmap.Config.ARGB_8888
                    )
                    try {
                        page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                        bitmaps.add(bitmap)
                    } catch (error: Exception) {
                        bitmap.recycle()
                        throw error
                    }
                } finally {
                    page.close()
                }
            }
            bitmaps.toList()
        } catch (error: Exception) {
            bitmaps.forEach(Bitmap::recycle)
            throw error
        } finally {
            try {
                renderer?.close()
            } finally {
                descriptor?.close()
            }
        }
    }
}
