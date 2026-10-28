package init.peit.data.util

import init.peit.data.local.entity.ReceiptEntity
import java.math.BigDecimal

object ReceiptContract {
    private val numericPrefix = Regex("^[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?")

    fun canonicalize(receipt: ReceiptEntity): ReceiptEntity =
        receipt.copy(packSize = canonicalPackSize(receipt.packSize))

    fun canonicalPackSize(value: String): String {
        val trimmed = value.trim()
        val number = trimmed.toBigDecimalOrNull()
            ?: numericPrefix.find(trimmed)?.value?.toBigDecimalOrNull()
            ?: throw IllegalArgumentException("Pack size must begin with a numeric value.")
        require(number.signum() > 0) { "Pack size must be greater than zero." }
        return number.stripTrailingZeros().toPlainString()
    }
}
