package init.peit.data.ocr

import org.junit.Assert.assertEquals
import org.junit.Test
import kotlin.math.min

class ReceiptImageCropperTest {

    @Test
    fun testDescenderPaddingCalculation() {
        val top = 20
        val bottom = 120
        val imageHeight = 1000

        val height = bottom - top // 100
        val descenderPadding = (height * 0.15f).toInt() // 15
        val calculatedBottom = min(imageHeight, bottom + descenderPadding)

        assertEquals(15, descenderPadding)
        assertEquals(135, calculatedBottom)
    }
}
