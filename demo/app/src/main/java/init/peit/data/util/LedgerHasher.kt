package init.peit.data.util

import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import java.security.MessageDigest
import java.util.Locale

object LedgerHasher {

    fun computeEntryId(
        receiptId: String,
        item: String,
        paidTotal: Double,
        receiptDate: String
    ): String {
        val normalizedAmount = when {
            paidTotal.isNaN() -> "nan"
            paidTotal == Double.POSITIVE_INFINITY -> "inf"
            paidTotal == Double.NEGATIVE_INFINITY -> "-inf"
            paidTotal == 0.0 -> "0.000000"
            else -> String.format(Locale.US, "%.6f", paidTotal)
        }
        val seed = "${receiptId.trim()}|${item.trim()}|$normalizedAmount|${receiptDate.trim()}"
        return sha256(seed)
    }

    fun computeEntryId(receipt: ReceiptEntity): String =
        computeEntryId(
            receiptId = receipt.receiptId,
            item = receipt.item,
            paidTotal = receipt.paidTotal,
            receiptDate = receipt.receiptDate
        )

    fun computeLegacyEntryId(receipt: ReceiptEntity): String =
        sha256("${receipt.receiptId}|${receipt.item}|${receipt.paidTotal}|${receipt.receiptDate}")

    fun sha256(input: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(input.toByteArray(Charsets.UTF_8))
        return bytes.joinToString("") { "%02x".format(it) }
    }

    fun verifyIntegrity(ledgerEntry: LedgerEntity, receipt: ReceiptEntity): Boolean =
        (ledgerEntry.entryId == computeEntryId(receipt) ||
            ledgerEntry.entryId == computeLegacyEntryId(receipt)) &&
            ledgerEntry.receiptId == receipt.receiptId &&
            ledgerEntry.item == receipt.item &&
            ledgerEntry.paidTotal == receipt.paidTotal &&
            ledgerEntry.receiptDate == receipt.receiptDate

    /**
     * Returns entries from genesis to tip, or null when the predecessor links do not form
     * exactly one complete chain. Timestamps are deliberately not used for ordering.
     */
    fun orderedChain(entries: List<LedgerEntity>): List<LedgerEntity>? {
        if (entries.isEmpty()) return emptyList()
        if (entries.map { it.entryId }.toSet().size != entries.size) return null

        val roots = entries.filter { it.previousHash == null }
        if (roots.size != 1) return null

        val children = entries
            .filter { it.previousHash != null }
            .groupBy { it.previousHash }
        if (children.values.any { it.size > 1 }) return null

        val ordered = mutableListOf<LedgerEntity>()
        val visited = mutableSetOf<String>()
        var current: LedgerEntity? = roots.single()
        while (current != null) {
            if (!visited.add(current.entryId)) return null
            ordered += current
            val child = children[current.entryId]?.singleOrNull() ?: break
            current = child
        }

        return ordered.takeIf { visited.size == entries.size }
    }
}
