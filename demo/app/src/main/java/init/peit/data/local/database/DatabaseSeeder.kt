package init.peit.data.local.database

import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.ReceiptRepository
import kotlinx.coroutines.flow.first

object DatabaseSeeder {

    private const val DEMO_NOTE =
        "Synthetic/demo data only; quality tiers and ratings are provisional defaults, not observations."

    suspend fun seedIfEmpty(receiptRepository: ReceiptRepository) {
        if (receiptRepository.getAllReceipts().first().isNotEmpty()) return

        val receipts = listOf(
            ReceiptEntity(
                receiptId = "rcpt_base_001",
                receiptDate = "2026-01-10",
                merchant = "SuperMart Fresh",
                item = "Organic Milk 1L",
                brand = "Aura Farms",
                category = "Groceries",
                quantity = 2.0,
                packSize = "1",
                unit = "Liter",
                unitPrice = 3.50,
                currency = "USD",
                tax = -0.56,
                paidTotal = -7.56,
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_base_002",
                receiptDate = "2026-01-12",
                merchant = "SuperMart Fresh",
                item = "Whole Wheat Bread 500g",
                brand = "Daily Grain",
                category = "Groceries",
                quantity = 3.0,
                packSize = "500",
                unit = "g",
                unitPrice = 2.80,
                currency = "USD",
                discount = 0.40,
                tax = -0.60,
                paidTotal = -8.60,
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_base_003",
                receiptDate = "2026-01-15",
                merchant = "PowerGrid Utilities",
                item = "Residential Electricity Service",
                brand = "PowerGrid",
                category = "Utilities",
                quantity = 1.0,
                packSize = "1",
                unit = "kWh",
                unitPrice = 85.00,
                currency = "USD",
                fee = -2.50,
                tax = -6.80,
                paidTotal = -94.30,
                eventType = "recurring",
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_base_004",
                receiptDate = "2026-01-20",
                merchant = "City Metro Transit",
                item = "Monthly Commuter Pass",
                brand = "CityRail",
                category = "Transportation",
                quantity = 1.0,
                packSize = "1",
                unit = "pass",
                unitPrice = 65.00,
                currency = "USD",
                discount = 5.00,
                tax = -4.80,
                paidTotal = -64.80,
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_base_005",
                receiptDate = "2026-01-25",
                merchant = "HealthCare Pharmacy",
                item = "Multivitamin Complex 90s",
                brand = "VitalLife",
                category = "Health & Beauty",
                quantity = 1.0,
                packSize = "90",
                unit = "count",
                unitPrice = 18.50,
                currency = "USD",
                discount = 2.00,
                tax = -1.32,
                paidTotal = -17.82,
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_curr_001",
                receiptDate = "2026-10-05",
                merchant = "SuperMart Fresh",
                item = "Organic Milk 1L",
                brand = "Aura Farms",
                category = "Groceries",
                quantity = 2.0,
                packSize = "1",
                unit = "Liter",
                unitPrice = 3.95,
                currency = "USD",
                tax = -0.63,
                paidTotal = -8.53,
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_curr_002",
                receiptDate = "2026-10-08",
                merchant = "SuperMart Fresh",
                item = "Whole Wheat Bread 500g",
                brand = "Daily Grain",
                category = "Groceries",
                quantity = 3.0,
                packSize = "500",
                unit = "g",
                unitPrice = 3.10,
                currency = "USD",
                tax = -0.74,
                paidTotal = -10.04,
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_curr_003",
                receiptDate = "2026-10-12",
                merchant = "PowerGrid Utilities",
                item = "Residential Electricity Service",
                brand = "PowerGrid",
                category = "Utilities",
                quantity = 1.0,
                packSize = "1",
                unit = "kWh",
                unitPrice = 92.50,
                currency = "USD",
                fee = -2.50,
                tax = -7.40,
                paidTotal = -102.40,
                eventType = "recurring",
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_curr_004",
                receiptDate = "2026-10-18",
                merchant = "City Metro Transit",
                item = "Monthly Commuter Pass",
                brand = "CityRail",
                category = "Transportation",
                quantity = 1.0,
                packSize = "1",
                unit = "pass",
                unitPrice = 68.00,
                currency = "USD",
                tax = -5.44,
                paidTotal = -73.44,
                notes = DEMO_NOTE
            ),
            ReceiptEntity(
                receiptId = "rcpt_curr_005",
                receiptDate = "2026-10-21",
                merchant = "HealthCare Pharmacy",
                item = "Multivitamin Complex 90s",
                brand = "VitalLife",
                category = "Health & Beauty",
                quantity = 1.0,
                packSize = "90",
                unit = "count",
                unitPrice = 19.99,
                currency = "USD",
                discount = 1.00,
                tax = -1.52,
                paidTotal = -20.51,
                notes = DEMO_NOTE
            )
        )

        receiptRepository.addReceiptsWithLedger(receipts)
    }
}
