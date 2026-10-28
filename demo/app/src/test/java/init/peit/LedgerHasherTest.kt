package init.peit

import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.util.LedgerHasher
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LedgerHasherTest {

    @Test
    fun computeEntryId_matchesCanonicalPythonVectorAndTrimsText() {
        assertEquals(
            "7a8ac87e9eccfe80c673d4e912c7d779d733d523c28ad3849ebab28749024bf4",
            LedgerHasher.computeEntryId(" REC-1 ", " Item ", -1.2, " 2026-01-01 ")
        )
    }

    @Test
    fun computeEntryId_formatsSixDecimalsAndClampsNegativeZero() {
        val base = LedgerHasher.computeEntryId("id", "item", 1.2345674, "date")
        assertEquals(base, LedgerHasher.computeEntryId("id", "item", 1.23456749, "date"))
        assertFalse(base == LedgerHasher.computeEntryId("id", "item", 1.234568, "date"))
        assertEquals(
            LedgerHasher.computeEntryId("id", "item", 0.0, "date"),
            LedgerHasher.computeEntryId("id", "item", -0.0, "date")
        )
    }

    @Test
    fun verifyIntegrity_checksOnlyCanonicalIdentityFields() {
        val receipt = ReceiptEntity(
            receiptId = "REC-2001",
            item = "Whole Wheat Bread",
            paidTotal = -3.49,
            receiptDate = "2026-10-22"
        )
        val entry = LedgerEntity(
            entryId = LedgerHasher.computeEntryId(receipt),
            receiptId = receipt.receiptId,
            item = receipt.item,
            paidTotal = receipt.paidTotal,
            receiptDate = receipt.receiptDate
        )

        assertTrue(LedgerHasher.verifyIntegrity(entry, receipt.copy(category = "Bakery", notes = "edited label")))
        assertFalse(LedgerHasher.verifyIntegrity(entry, receipt.copy(item = "Other bread")))
        assertFalse(LedgerHasher.verifyIntegrity(entry, receipt.copy(paidTotal = -0.99)))
        assertFalse(LedgerHasher.verifyIntegrity(entry, receipt.copy(receiptDate = "2026-10-23")))
    }

    @Test
    fun verifyIntegrity_recognizesPreservedLegacyHashWithoutReplacingIt() {
        val receipt = ReceiptEntity(
            receiptId = "legacy-1",
            item = "Item",
            paidTotal = -1.2,
            receiptDate = "2026-01-01"
        )
        val legacyId = LedgerHasher.computeLegacyEntryId(receipt)
        val entry = LedgerEntity(
            entryId = legacyId,
            receiptId = receipt.receiptId,
            item = receipt.item,
            paidTotal = receipt.paidTotal,
            receiptDate = receipt.receiptDate
        )

        assertTrue(LedgerHasher.verifyIntegrity(entry, receipt))
        assertFalse(legacyId == LedgerHasher.computeEntryId(receipt))
        assertEquals(legacyId, entry.entryId)
    }

    @Test
    fun orderedChain_ordersByLinksEvenWhenTimestampsTie() {
        val chain = listOf(
            entry("second", "first", timestamp = 5),
            entry("first", null, timestamp = 5),
            entry("third", "second", timestamp = 4)
        )

        assertEquals(listOf("first", "second", "third"), LedgerHasher.orderedChain(chain)?.map { it.entryId })
    }

    @Test
    fun orderedChain_rejectsMultipleGenesisNodes() {
        assertNull(LedgerHasher.orderedChain(listOf(entry("first", null), entry("second", null))))
    }

    @Test
    fun orderedChain_rejectsMissingPredecessor() {
        assertNull(LedgerHasher.orderedChain(listOf(entry("first", null), entry("orphan", "missing"))))
    }

    @Test
    fun orderedChain_rejectsCyclesAndForks() {
        assertNull(
            LedgerHasher.orderedChain(
                listOf(entry("root", null), entry("cycle-a", "cycle-b"), entry("cycle-b", "cycle-a"))
            )
        )
        assertNull(
            LedgerHasher.orderedChain(
                listOf(entry("root", null), entry("child-a", "root"), entry("child-b", "root"))
            )
        )
    }

    private fun entry(id: String, previous: String?, timestamp: Long = 1) = LedgerEntity(
        entryId = id,
        receiptId = id,
        item = "item",
        paidTotal = -1.0,
        receiptDate = "2026-01-01",
        previousHash = previous,
        timestamp = timestamp
    )
}
