package init.peit.ui.verification

import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.ReceiptRepository
import init.peit.domain.model.ParsedReceipt
import init.peit.domain.model.ParsedReceiptItem
import init.peit.domain.service.HistoricalAttributeInheritanceService
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ReceiptVerificationViewModelTest {
    private val testDispatcher = StandardTestDispatcher()
    private lateinit var fakeRepository: FakeReceiptRepository
    private lateinit var viewModel: ReceiptVerificationViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        fakeRepository = FakeReceiptRepository()
        viewModel = ReceiptVerificationViewModel(
            fakeRepository,
            HistoricalAttributeInheritanceService(fakeRepository)
        )
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun startingManualReceiptClearsPreviouslySavedReceiptWithoutWriting() = runTest {
        viewModel.loadParsedReceipt(receipt("Previous", 3.00))
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.markLabelsReviewed(true)
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(viewModel.uiState.value.isSaved)

        viewModel.startManualReceipt()

        assertEquals(ReceiptVerificationUiState(), viewModel.uiState.value)
        assertEquals(1, fakeRepository.batchCallCount)
    }

    @Test
    fun loadingSecondReceiptResetsSavedAndErrorState() = runTest {
        viewModel.loadParsedReceipt(receipt("First", 3.05))
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.markLabelsReviewed(true)
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(viewModel.uiState.value.isSaved)
        assertTrue(viewModel.uiState.value.saveSuccessEventPending)

        viewModel.consumeSaveSuccess()
        viewModel.loadParsedReceipt(receipt("Invalid", 2.00))
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.updateDate("not-a-date")
        viewModel.saveReceiptAndLedger()
        assertNotNull(viewModel.uiState.value.errorMessage)

        viewModel.loadParsedReceipt(receipt("Second", 4.00))
        val immediatelyReset = viewModel.uiState.value
        assertFalse(immediatelyReset.isSaved)
        assertFalse(immediatelyReset.isSaving)
        assertFalse(immediatelyReset.saveSuccessEventPending)
        assertEquals(emptyList<LedgerEntity>(), immediatelyReset.savedLedgerEntries)
        assertEquals(null, immediatelyReset.errorMessage)
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals("Second", viewModel.uiState.value.merchant)
        assertFalse(viewModel.uiState.value.isSaved)

        viewModel.markLabelsReviewed(true)
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(viewModel.uiState.value.isSaved)
        assertEquals(2, fakeRepository.batchCallCount)
    }

    @Test
    fun mismatchedObservedPaymentBlocksSaveWithoutReconciliation() = runTest {
        viewModel.loadParsedReceipt(
            receipt(
                merchant = "Mismatch",
                paidTotal = 5.00,
                items = listOf(ParsedReceiptItem(itemName = "Item", unitPrice = 4.00, linePrice = 4.00))
            )
        )
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.markLabelsReviewed(true)
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(5.00, viewModel.uiState.value.paidTotal, 0.0)
        assertFalse(viewModel.uiState.value.isSaved)
        assertEquals(0, fakeRepository.batchCallCount)
        assertTrue(viewModel.uiState.value.errorMessage.orEmpty().contains("out of balance"))
    }

    @Test
    fun oneBatchAllocatesSignedAdjustmentsAndCorrectsCentRemainders() = runTest {
        val items = listOf(
            ParsedReceiptItem(itemName = "A", unitPrice = 1.0, linePrice = 1.0),
            ParsedReceiptItem(itemName = "B", unitPrice = 1.0, linePrice = 1.0),
            ParsedReceiptItem(itemName = "C", unitPrice = 1.0, linePrice = 1.0)
        )
        val allocations = ReceiptMoneyAllocator.allocate(
            items = items,
            discount = 0.02,
            tax = -0.04,
            fee = -0.02,
            deposit = -0.01,
            paidTotal = 3.05
        )

        assertEquals(listOf(0.01, 0.01, 0.00), allocations.map { it.discount.toDouble() })
        assertEquals(listOf(-0.01, -0.01, -0.02), allocations.map { it.tax.toDouble() })
        assertEquals(listOf(-0.01, -0.01, 0.00), allocations.map { it.fee.toDouble() })
        assertEquals(listOf(0.00, 0.00, -0.01), allocations.map { it.deposit.toDouble() })
        assertEquals(-3.05, allocations.sumOf { it.paidTotal.toDouble() }, 0.000001)

        viewModel.loadParsedReceipt(
            receipt(
                merchant = "Allocation",
                paidTotal = 3.05,
                items = items,
                discount = 0.02,
                tax = -0.04,
                fee = -0.02,
                deposit = -0.01
            )
        )
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.markLabelsReviewed(true)
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, fakeRepository.batchCallCount)
        assertEquals(3, fakeRepository.lastBatch.size)
        assertEquals(-3.05, fakeRepository.lastBatch.sumOf { it.paidTotal }, 0.000001)
        assertEquals(0.02, fakeRepository.lastBatch.sumOf { it.discount }, 0.000001)
        assertEquals(-0.04, fakeRepository.lastBatch.sumOf { it.tax }, 0.000001)
        assertEquals(-0.02, fakeRepository.lastBatch.sumOf { it.fee }, 0.000001)
        assertEquals(-0.01, fakeRepository.lastBatch.sumOf { it.deposit }, 0.000001)
        assertTrue(
            fakeRepository.lastBatch.all {
                it.eventType == "one_off" &&
                    it.availability == "in_stock" &&
                    it.paidTotal <= 0.0 &&
                    it.notes.contains("Analyst labels reviewed by user")
            }
        )
    }

    @Test
    fun duplicateCallsWhileSavingAndAfterSuccessUseOneBatch() = runTest {
        val gate = CompletableDeferred<Unit>()
        fakeRepository.saveGate = gate
        viewModel.loadParsedReceipt(receipt("Locked", 3.00))
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.markLabelsReviewed(true)

        viewModel.saveReceiptAndLedger()
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(viewModel.uiState.value.isSaving)
        assertEquals(1, fakeRepository.batchCallCount)

        gate.complete(Unit)
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(viewModel.uiState.value.isSaved)
        assertEquals(1, fakeRepository.batchCallCount)
    }

    @Test
    fun batchFailureIsReportedAndNotMarkedSaved() = runTest {
        fakeRepository.failBatch = true
        viewModel.loadParsedReceipt(receipt("Failure", 3.00))
        testDispatcher.scheduler.advanceUntilIdle()
        viewModel.markLabelsReviewed(true)
        viewModel.saveReceiptAndLedger()
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, fakeRepository.batchCallCount)
        assertFalse(viewModel.uiState.value.isSaved)
        assertFalse(viewModel.uiState.value.isSaving)
        assertTrue(viewModel.uiState.value.errorMessage.orEmpty().contains("batch failure"))
    }

    @Test
    fun historicalLookupFailureIsVisibleWhileReceiptRemainsReviewable() = runTest {
        fakeRepository.historyError = IllegalStateException("history unavailable")
        viewModel.loadParsedReceipt(receipt("History Failure", 3.00))
        testDispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModel.uiState.value.isLoading)
        assertEquals("History Failure", viewModel.uiState.value.merchant)
        assertTrue(viewModel.uiState.value.warningMessage.orEmpty().contains("history unavailable"))
    }

    @Test
    fun validatorRejectsUnknownMetadataEmptyItemsAndNonCanonicalLabels() {
        val validState = ReceiptVerificationUiState(
            merchant = "Market",
            date = "2026-10-22",
            currency = "USD",
            items = listOf(ParsedReceiptItem(itemName = "Beans", unitPrice = 2.0, linePrice = 2.0)),
            paidTotal = 2.0,
            labelsReviewed = true
        )
        assertEquals(null, ReceiptVerificationValidator.validate(validState))
        assertTrue(ReceiptVerificationValidator.validate(validState.copy(date = "")).orEmpty().contains("date"))
        assertTrue(ReceiptVerificationValidator.validate(validState.copy(currency = "GBP")).orEmpty().contains("MXN"))
        assertTrue(ReceiptVerificationValidator.validate(validState.copy(items = emptyList())).orEmpty().contains("item"))
        assertTrue(
            ReceiptVerificationValidator.validate(
                validState.copy(items = listOf(validState.items.single().copy(brandTier = "Tier B")))
            ).orEmpty().contains("tiers")
        )
    }

    private fun receipt(
        merchant: String,
        paidTotal: Double,
        items: List<ParsedReceiptItem> = listOf(
            ParsedReceiptItem(itemName = "Item", unitPrice = paidTotal, linePrice = paidTotal)
        ),
        discount: Double = 0.0,
        tax: Double = 0.0,
        fee: Double = 0.0,
        deposit: Double = 0.0
    ) = ParsedReceipt(
        merchant = merchant,
        date = "2026-10-22",
        currency = "USD",
        items = items,
        discount = discount,
        tax = tax,
        fee = fee,
        deposit = deposit,
        paidTotal = paidTotal
    )

    private class FakeReceiptRepository : ReceiptRepository {
        val receiptsList = mutableListOf<ReceiptEntity>()
        val ledgerList = mutableListOf<LedgerEntity>()
        var batchCallCount = 0
        var lastBatch: List<ReceiptEntity> = emptyList()
        var saveGate: CompletableDeferred<Unit>? = null
        var failBatch = false
        var historyError: Exception? = null

        override fun getAllReceipts(): Flow<List<ReceiptEntity>> =
            historyError?.let { error -> flow { throw error } } ?: flowOf(receiptsList)
        override fun getReceiptsBetweenDates(startDate: String, endDate: String): Flow<List<ReceiptEntity>> = flowOf(receiptsList)
        override suspend fun getReceiptsBetweenDatesSync(startDate: String, endDate: String): List<ReceiptEntity> = receiptsList
        override fun getReceiptById(receiptId: String): Flow<ReceiptEntity?> = flowOf(receiptsList.find { it.receiptId == receiptId })
        override suspend fun getReceiptByIdSync(receiptId: String): ReceiptEntity? = receiptsList.find { it.receiptId == receiptId }
        override suspend fun insertReceipt(receipt: ReceiptEntity) { receiptsList.add(receipt) }
        override suspend fun insertReceipts(receipts: List<ReceiptEntity>) { receiptsList.addAll(receipts) }
        override suspend fun updateReceipt(receipt: ReceiptEntity) {}
        override suspend fun deleteReceipt(receipt: ReceiptEntity) {}
        override suspend fun deleteReceiptById(receiptId: String) {}
        override suspend fun deleteAllReceipts() { receiptsList.clear() }
        override fun getAllLedgerEntries(): Flow<List<LedgerEntity>> = flowOf(ledgerList)
        override fun getLedgerEntryById(entryId: String): Flow<LedgerEntity?> = flowOf(ledgerList.find { it.entryId == entryId })
        override fun getLedgerEntriesByReceiptId(receiptId: String): Flow<List<LedgerEntity>> =
            flowOf(ledgerList.filter { it.receiptId == receiptId })
        override suspend fun getLedgerEntryByIdSync(entryId: String): LedgerEntity? = ledgerList.find { it.entryId == entryId }
        override suspend fun insertLedgerEntry(entry: LedgerEntity) { ledgerList.add(entry) }
        override suspend fun addReceiptWithLedger(receipt: ReceiptEntity): LedgerEntity =
            addReceiptsWithLedger(listOf(receipt)).single()
        override suspend fun addReceiptsWithLedger(receipts: List<ReceiptEntity>): List<LedgerEntity> {
            batchCallCount++
            lastBatch = receipts
            saveGate?.await()
            if (failBatch) error("simulated batch failure")
            val newLedgers = receipts.map { receipt ->
                LedgerEntity(
                    entryId = "signed_ledger_${receipt.receiptId}",
                    receiptId = receipt.receiptId,
                    item = receipt.item,
                    paidTotal = receipt.paidTotal,
                    receiptDate = receipt.receiptDate,
                    isValid = true
                )
            }
            receiptsList.addAll(receipts)
            ledgerList.addAll(newLedgers)
            return newLedgers
        }
        override suspend fun verifyLedgerIntegrity(): Boolean = true
    }
}
