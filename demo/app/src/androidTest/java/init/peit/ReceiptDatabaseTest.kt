package init.peit

import android.content.Context
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import init.peit.data.local.database.AppDatabase
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.ReceiptRepositoryImpl
import init.peit.data.util.LedgerHasher
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ReceiptDatabaseTest {

    private val context: Context
        get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun migrationPreservesReceiptAndConvertsLegacyAvailabilityAndPackSize() {
        val name = "receipt-migration-test.db"
        context.deleteDatabase(name)
        val legacy = context.openOrCreateDatabase(name, Context.MODE_PRIVATE, null)
        legacy.execSQL(
            """
            CREATE TABLE receipts (
                receipt_id TEXT NOT NULL PRIMARY KEY,
                receipt_date TEXT NOT NULL,
                merchant TEXT NOT NULL,
                item TEXT NOT NULL,
                brand TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL NOT NULL,
                pack_size TEXT NOT NULL,
                unit TEXT NOT NULL,
                unit_price REAL NOT NULL,
                currency TEXT NOT NULL,
                discount REAL NOT NULL,
                fee REAL NOT NULL,
                tax REAL NOT NULL,
                deposit REAL NOT NULL,
                paid_total REAL NOT NULL,
                event_type TEXT NOT NULL,
                store_tier TEXT NOT NULL,
                store_rating REAL NOT NULL,
                brand_tier TEXT NOT NULL,
                brand_rating REAL NOT NULL,
                product_tier TEXT NOT NULL,
                product_rating REAL NOT NULL,
                availability INTEGER NOT NULL,
                notes TEXT NOT NULL
            )
            """.trimIndent()
        )
        legacy.execSQL(
            """
            CREATE TABLE ledger_entries (
                entry_id TEXT NOT NULL PRIMARY KEY,
                receipt_id TEXT NOT NULL,
                item TEXT NOT NULL,
                paid_total REAL NOT NULL,
                receipt_date TEXT NOT NULL,
                previous_hash TEXT,
                timestamp INTEGER NOT NULL,
                is_valid INTEGER NOT NULL
            )
            """.trimIndent()
        )
        legacy.execSQL(
            "INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            arrayOf<Any>(
                "legacy-1", "2026-01-01", "Example", "Item", "Brand", "Food", 2.0, "1L", "Liter",
                1.5, "USD", 0.0, 0.0, 0.0, 0.0, -3.0, "one_off", "C", 3.0, "C", 3.0, "C", 3.0,
                0, "legacy note"
            )
        )
        val legacyReceipt = ReceiptEntity(
            receiptId = "legacy-1",
            receiptDate = "2026-01-01",
            item = "Item",
            paidTotal = -3.0,
            packSize = "1L",
            unit = "Liter",
            availability = "out_of_stock",
            notes = "legacy note"
        )
        val legacyEntry = LedgerEntity(
            entryId = LedgerHasher.computeLegacyEntryId(legacyReceipt),
            receiptId = legacyReceipt.receiptId,
            item = legacyReceipt.item,
            paidTotal = legacyReceipt.paidTotal,
            receiptDate = legacyReceipt.receiptDate
        )
        legacy.execSQL(
            "INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            arrayOf<Any?>(
                legacyEntry.entryId,
                legacyEntry.receiptId,
                legacyEntry.item,
                legacyEntry.paidTotal,
                legacyEntry.receiptDate,
                legacyEntry.previousHash,
                legacyEntry.timestamp,
                if (legacyEntry.isValid) 1 else 0
            )
        )
        legacy.version = 1
        legacy.close()

        val database = Room.databaseBuilder(context, AppDatabase::class.java, name)
            .addMigrations(AppDatabase.MIGRATION_1_2)
            .build()
        try {
            val migrated = runBlocking { database.receiptDao().getAllReceipts().first().single() }
            assertEquals("legacy-1", migrated.receiptId)
            assertEquals("Item", migrated.item)
            assertEquals("1.0", migrated.packSize)
            assertEquals("Liter", migrated.unit)
            assertEquals("out_of_stock", migrated.availability)
            assertEquals("legacy note", migrated.notes)
            val migratedEntry = runBlocking { database.ledgerDao().getAllLedgerEntries().first().single() }
            assertEquals(legacyEntry.entryId, migratedEntry.entryId)
            assertTrue(runBlocking { ReceiptRepositoryImpl(database).verifyLedgerIntegrity() })
        } finally {
            database.close()
            context.deleteDatabase(name)
        }
    }

    @Test
    fun failedLedgerInsertRollsBackReceiptAndLedgerBatch() {
        val database = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        try {
            database.openHelper.writableDatabase.execSQL(
                """
                CREATE TRIGGER reject_ledger_insert
                BEFORE INSERT ON ledger_entries
                BEGIN
                    SELECT RAISE(ABORT, 'test rollback');
                END
                """.trimIndent()
            )
            val repository = ReceiptRepositoryImpl(database)
            val receipt = ReceiptEntity(
                receiptId = "rollback-1",
                item = "Synthetic test item",
                paidTotal = -1.0,
                receiptDate = "2026-01-01"
            )

            try {
                runBlocking { repository.addReceiptsWithLedger(listOf(receipt)) }
                throw AssertionError("Expected the test trigger to abort the ledger insert")
            } catch (_: Exception) {
                assertNull(runBlocking { database.receiptDao().getReceiptByIdSync(receipt.receiptId) })
                assertTrue(runBlocking { database.ledgerDao().getAllLedgerEntries().first().isEmpty() })
            }
        } finally {
            database.close()
        }
    }
}
