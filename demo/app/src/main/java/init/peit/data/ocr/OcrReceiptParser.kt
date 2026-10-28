package init.peit.data.ocr

import android.graphics.Rect
import com.google.mlkit.vision.text.Text
import init.peit.domain.model.ParsedReceipt
import init.peit.domain.model.ParsedReceiptItem
import java.util.Locale
import java.util.regex.Pattern

data class SpatialElement(
    val text: String,
    val boundingBox: Rect? = null
)

data class SpatialLine(
    val elements: List<SpatialElement>,
    val boundingBox: Rect? = null
) {
    val text: String get() = elements.joinToString(" ") { it.text }.trim()
}

class OcrReceiptParser {

    /**
     * Parses ML Kit Text object into a ParsedReceipt structure.
     */
    fun parse(mlKitText: Text): ParsedReceipt {
        val spatialLines = buildSpatialLinesFromMlKit(mlKitText)
        return parseSpatialLines(spatialLines, mlKitText.text)
    }

    /**
     * Parses raw text string (for testing or non-ML Kit usage).
     */
    fun parseRawText(rawText: String): ParsedReceipt {
        val lines = rawText.lines().map { it.trim() }.filter { it.isNotEmpty() }
        val spatialLines = lines.mapIndexed { index, line ->
            val rect = Rect(0, index * 20, 100, (index + 1) * 20)
            SpatialLine(
                elements = listOf(SpatialElement(text = line, boundingBox = rect)),
                boundingBox = rect
            )
        }
        return parseSpatialLines(spatialLines, rawText)
    }

    /**
     * Convert ML Kit Text blocks/lines into spatially sorted lines.
     */
    fun buildSpatialLinesFromMlKit(mlKitText: Text): List<SpatialLine> {
        val allElements = mutableListOf<SpatialElement>()
        for (block in mlKitText.textBlocks) {
            for (line in block.lines) {
                for (element in line.elements) {
                    allElements.add(
                        SpatialElement(
                            text = element.text,
                            boundingBox = element.boundingBox
                        )
                    )
                }
            }
        }

        if (allElements.isEmpty()) return emptyList()

        // Sort elements primarily by top bounding box
        val sortedElements = allElements.sortedBy { it.boundingBox?.top ?: 0 }

        val lines = mutableListOf<MutableList<SpatialElement>>()
        for (elem in sortedElements) {
            val elemBox = elem.boundingBox
            var added = false
            if (elemBox != null) {
                for (line in lines) {
                    val firstBox = line.first().boundingBox
                    if (firstBox != null) {
                        val elemMid = (elemBox.top + elemBox.bottom) / 2.0
                        val lineMid = (firstBox.top + firstBox.bottom) / 2.0
                        val avgHeight = (elemBox.height() + firstBox.height()) / 2.0
                        if (Math.abs(elemMid - lineMid) < Math.max(avgHeight * 0.6, 10.0)) {
                            line.add(elem)
                            added = true
                            break
                        }
                    }
                }
            }
            if (!added) {
                lines.add(mutableListOf(elem))
            }
        }

        return lines.map { elemList ->
            val sortedList = elemList.sortedBy { it.boundingBox?.left ?: 0 }
            val unionRect = sortedList.mapNotNull { it.boundingBox }.reduceOrNull { acc, rect ->
                Rect(
                    Math.min(acc.left, rect.left),
                    Math.min(acc.top, rect.top),
                    Math.max(acc.right, rect.right),
                    Math.max(acc.bottom, rect.bottom)
                )
            }
            SpatialLine(elements = sortedList, boundingBox = unionRect)
        }.sortedBy { it.boundingBox?.top ?: 0 }
    }

    fun parseSpatialLines(spatialLines: List<SpatialLine>, fullRawText: String): ParsedReceipt {
        val lineTexts = spatialLines.map { it.text }

        val currency = detectCurrency(fullRawText, lineTexts)
        val merchant = extractMerchant(spatialLines)
        val date = extractDate(fullRawText)

        var tax = 0.0
        var discount = 0.0
        var fee = 0.0
        var deposit = 0.0
        var paidTotal = 0.0
        var subtotal = 0.0

        val items = mutableListOf<ParsedReceiptItem>()

        for (spatialLine in spatialLines) {
            val lineText = spatialLine.text
            val upperLine = lineText.uppercase(Locale.ROOT)

            when {
                TAX_PATTERN.matcher(upperLine).find() -> {
                    extractPriceValue(lineText)?.let { tax = -kotlin.math.abs(it) }
                }
                DISCOUNT_PATTERN.matcher(upperLine).find() -> {
                    extractPriceValue(lineText)?.let { discount = Math.abs(it) }
                }
                FEE_PATTERN.matcher(upperLine).find() -> {
                    extractPriceValue(lineText)?.let { fee = -kotlin.math.abs(it) }
                }
                DEPOSIT_PATTERN.matcher(upperLine).find() -> {
                    extractPriceValue(lineText)?.let { deposit = -kotlin.math.abs(it) }
                }
                TOTAL_PATTERN.matcher(upperLine).find() -> {
                    extractPriceValue(lineText)?.let { paidTotal = it }
                }
                SUBTOTAL_PATTERN.matcher(upperLine).find() -> {
                    extractPriceValue(lineText)?.let { subtotal = it }
                }
                else -> {
                    // Attempt item parsing
                    val item = parseLineItem(spatialLine)
                    if (item != null) {
                        items.add(item)
                    }
                }
            }
        }

        return ParsedReceipt(
            merchant = merchant,
            date = date,
            currency = currency,
            items = items,
            subtotal = subtotal,
            tax = tax,
            discount = discount,
            fee = fee,
            deposit = deposit,
            paidTotal = paidTotal,
            rawText = fullRawText
        )
    }

    private fun detectCurrency(rawText: String, lines: List<String>): String {
        val upper = rawText.uppercase(Locale.ROOT)
        if (upper.contains("MXN") || upper.contains("M.N.") || upper.contains("PESO") || upper.contains("PESOS") || upper.contains("IVA") || upper.contains("RFC ")) {
            return "MXN"
        }
        if (upper.contains("EUR") || upper.contains("€")) {
            return "EUR"
        }
        if (upper.contains("USD") || upper.contains("US$")) {
            return "USD"
        }

        // Check for merchant heuristics
        if (lines.any { l ->
            val u = l.uppercase()
            u.contains("WALMART") || u.contains("SORIANA") || u.contains("OXXO") || u.contains("CHEDRAUI") || u.contains("BODEGA")
        }) {
            return "MXN"
        }

        return "USD"
    }

    private fun extractMerchant(spatialLines: List<SpatialLine>): String {
        val candidates = spatialLines.take(6)
        for (spatialLine in candidates) {
            val text = spatialLine.text
            val upper = text.uppercase(Locale.ROOT)
            if (IGNORE_HEADER_PATTERN.matcher(upper).find()) continue
            if (PRICE_AT_END_PATTERN.matcher(text).find()) continue
            if (text.length in 3..40 && !text.matches(Regex(".*\\d{2}/\\d{2}.*"))) {
                // Return clean merchant string
                return text.replace(Regex("[^a-zA-Z0-9&\\s\\-.]"), "").trim()
            }
        }
        return ""
    }

    private fun extractDate(rawText: String): String {
        val matcher = DATE_PATTERN.matcher(rawText)
        if (matcher.find()) {
            val rawDate = matcher.group(0) ?: ""
            return normalizeDate(rawDate)
        }
        return ""
    }

    private fun normalizeDate(rawDate: String): String {
        val digits = rawDate.split(Regex("[/\\-\\.\\s]+")).filter { it.isNotEmpty() }
        if (digits.size >= 3) {
            val y: String
            val m: String
            val d: String
            if (digits[0].length == 4) {
                y = digits[0]
                m = digits[1].padStart(2, '0')
                d = digits[2].padStart(2, '0')
            } else {
                d = digits[0].padStart(2, '0')
                m = digits[1].padStart(2, '0')
                y = if (digits[2].length == 2) "20" + digits[2] else digits[2]
            }
            return "$y-$m-$d"
        }
        return rawDate
    }

    private fun parseLineItem(spatialLine: SpatialLine): ParsedReceiptItem? {
        val text = spatialLine.text
        if (text.length < 3) return null

        val upper = text.uppercase(Locale.ROOT)
        if (IGNORE_HEADER_PATTERN.matcher(upper).find() ||
            TAX_PATTERN.matcher(upper).find() ||
            TOTAL_PATTERN.matcher(upper).find() ||
            SUBTOTAL_PATTERN.matcher(upper).find()
        ) {
            return null
        }

        // Try extracting price from the end of the line
        val priceMatcher = PRICE_AT_END_PATTERN.matcher(text)
        if (!priceMatcher.find()) return null

        val priceStr = priceMatcher.group(1) ?: return null
        val observedLinePrice = parseMoney(priceStr) ?: return null

        // Remaining text before the price
        val namePart = text.substring(0, priceMatcher.start()).trim()
        if (namePart.isEmpty()) return null

        // Parse pack size and unit (e.g., 500g, 1.5kg, 1L, 12oz, 6 pack)
        var packSize = "1"
        var unit = "piece"
        val packSizeMatcher = PACK_SIZE_PATTERN.matcher(namePart)
        if (packSizeMatcher.find()) {
            val num = packSizeMatcher.group(1) ?: ""
            val u = packSizeMatcher.group(2) ?: ""
            packSize = "$num $u".trim()
            unit = u.lowercase(Locale.ROOT)
        }

        // Try parsing quantity & unit price from namePart or full line
        var quantity = 1.0
        var unitPrice = observedLinePrice
        var linePrice = observedLinePrice
        val qtyMatcher = QTY_X_PRICE_PATTERN.matcher(namePart)
        var cleanName = namePart

        if (qtyMatcher.find()) {
            val parsedQ = qtyMatcher.group(1)?.let(::parseMoney)
            val parsedP = qtyMatcher.group(2)?.let(::parseMoney)
            if (parsedQ != null && parsedQ > 0) quantity = parsedQ
            if (parsedP != null && parsedP > 0) unitPrice = parsedP
            cleanName = namePart.substring(0, qtyMatcher.start()) + " " + namePart.substring(qtyMatcher.end())
        } else {
            val quantityOnlyMatcher = QTY_X_ONLY_PATTERN.matcher(namePart)
            if (quantityOnlyMatcher.find()) {
                quantity = quantityOnlyMatcher.group(1)?.let(::parseMoney) ?: 1.0
                unitPrice = observedLinePrice
                linePrice = quantity * unitPrice
                cleanName = namePart.substring(0, quantityOnlyMatcher.start())
            }
        }

        cleanName = cleanName.replace(Regex("[$*#]"), "").replace(Regex("\\s+"), " ").trim()
        if (cleanName.length < 2) return null

        return ParsedReceiptItem(
            itemName = cleanName,
            quantity = quantity,
            unitPrice = unitPrice,
            linePrice = linePrice,
            packSize = packSize,
            unit = unit,
            boundingBox = spatialLine.boundingBox
        )
    }

    private fun extractPriceValue(text: String): Double? {
        val matcher = PRICE_PATTERN.matcher(text)
        var lastVal: Double? = null
        while (matcher.find()) {
            val str = matcher.group(1) ?: matcher.group(0)
            parseMoney(str)?.let { lastVal = it }
        }
        return lastVal
    }

    private fun parseMoney(raw: String): Double? {
        var value = raw
            .replace("$", "")
            .replace("€", "")
            .replace(Regex("(?i)EUR"), "")
            .replace(" ", "")
            .trim()
        if (value.isEmpty()) return null
        val lastComma = value.lastIndexOf(',')
        val lastDot = value.lastIndexOf('.')
        val decimalSeparator = when {
            lastComma >= 0 && lastDot >= 0 -> if (lastComma > lastDot) ',' else '.'
            lastComma >= 0 -> if (value.length - lastComma - 1 in 1..2) ',' else null
            lastDot >= 0 -> if (value.length - lastDot - 1 in 1..2) '.' else null
            else -> null
        }
        value = if (decimalSeparator == null) {
            value.replace(",", "").replace(".", "")
        } else {
            val thousandsSeparator = if (decimalSeparator == ',') '.' else ','
            value.replace(thousandsSeparator.toString(), "")
                .replace(decimalSeparator, '.')
        }
        return value.toDoubleOrNull()
    }

    companion object {
        private val TAX_PATTERN = Pattern.compile("\\b(TAX|IVA|IMPUESTO|VAT|IEPS)\\b")
        private val DISCOUNT_PATTERN = Pattern.compile("\\b(DISCOUNT|DESCUENTO|DCTO|AHORRO|SAVINGS|REBAJA)\\b")
        private val FEE_PATTERN = Pattern.compile("\\b(FEE|PROPINA|TIP|CARGO|SERVICE|COMISION)\\b")
        private val DEPOSIT_PATTERN = Pattern.compile("\\b(DEPOSIT|DEPOSITO|ENVASE|CONTAINER|CASCO)\\b")
        private val TOTAL_PATTERN = Pattern.compile("\\b(TOTAL|TOTAL PAGADO|PAGO|IMPORTE TOTAL|BALANCE DUE|AMOUNT PAID|GRAND TOTAL|SUMA)\\b")
        private val SUBTOTAL_PATTERN = Pattern.compile("\\b(SUBTOTAL|SUB TOTAL|SUB-TOTAL)\\b")

        private val IGNORE_HEADER_PATTERN = Pattern.compile(
            "\\b(TICKET|COMPROBANTE|BIENVENIDO|WELCOME|RFC|TEL|SUCURSAL|CASHIER|CAJERO|GRACIAS|THANK YOU|FECHA|DATE|HORA|TIME)\\b"
        )

        private val DATE_PATTERN = Pattern.compile(
            "\\b(\\d{2,4})[/\\-\\.](\\d{1,2})[/\\-\\.](\\d{2,4})\\b|\\b(\\d{1,2})\\s+(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC|JAN|APR|AUG|DEC)[A-Z]*\\s+(\\d{2,4})\\b",
            Pattern.CASE_INSENSITIVE
        )

        private val PRICE_AT_END_PATTERN = Pattern.compile("([\\$€]?\\s*\\d[\\d.,]*\\s*(?:€|EUR)?)\\s*$", Pattern.CASE_INSENSITIVE)
        private val PRICE_PATTERN = Pattern.compile("[\\$€]?\\s*(\\d[\\d.,]*)\\s*(?:€|EUR)?", Pattern.CASE_INSENSITIVE)
        private val QTY_X_PRICE_PATTERN = Pattern.compile("(\\d+(?:[.,]\\d+)?)\\s*(?:x|\\*)\\s*(\\d+(?:[.,]\\d+)?)\\s*$", Pattern.CASE_INSENSITIVE)
        private val QTY_X_ONLY_PATTERN = Pattern.compile("(\\d+(?:[.,]\\d+)?)\\s*(?:x|\\*)\\s*$", Pattern.CASE_INSENSITIVE)
        private val PACK_SIZE_PATTERN = Pattern.compile("(\\d+(?:\\.\\d+)?)\\s*(g|kg|ml|l|liter|litro|oz|lb|pcs|pza|pack|pk)\\b", Pattern.CASE_INSENSITIVE)
    }
}
