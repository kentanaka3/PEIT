package init.peit.data.local.database

import android.content.Context
import androidx.room.migration.Migration
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.sqlite.db.SupportSQLiteDatabase
import init.peit.data.local.dao.LedgerDao
import init.peit.data.local.dao.ReceiptDao
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity

@Database(
    entities = [
        ReceiptEntity::class,
        LedgerEntity::class
    ],
    version = 2,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun receiptDao(): ReceiptDao
    abstract fun ledgerDao(): LedgerDao

    companion object {
        // This schema migration does not regenerate ledger hashes or retroactively validate legacy entries.
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE receipts_new (
                        receipt_id TEXT NOT NULL,
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
                        availability TEXT NOT NULL,
                        notes TEXT NOT NULL,
                        PRIMARY KEY(receipt_id)
                    )
                    """.trimIndent()
                )
                db.execSQL(
                    """
                    INSERT INTO receipts_new (
                        receipt_id, receipt_date, merchant, item, brand, category, quantity,
                        pack_size, unit, unit_price, currency, discount, fee, tax, deposit,
                        paid_total, event_type, store_tier, store_rating, brand_tier, brand_rating,
                        product_tier, product_rating, availability, notes
                    )
                    SELECT
                        receipt_id, receipt_date, merchant, item, brand, category, quantity,
                        CASE WHEN CAST(pack_size AS REAL) > 0
                            THEN CAST(pack_size AS REAL)
                            ELSE 1
                        END,
                        unit, unit_price, currency, discount, fee, tax, deposit, paid_total,
                        event_type, store_tier, store_rating, brand_tier, brand_rating,
                        product_tier, product_rating,
                        CASE WHEN availability = 0 THEN 'out_of_stock' ELSE 'in_stock' END,
                        notes
                    FROM receipts
                    """.trimIndent()
                )
                db.execSQL("DROP TABLE receipts")
                db.execSQL("ALTER TABLE receipts_new RENAME TO receipts")
            }
        }

        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "peit_database"
                ).addMigrations(MIGRATION_1_2).build()
                INSTANCE = instance
                instance
            }
        }
    }
}
