package init.peit.ui.verification

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.ReceiptRepository
import init.peit.domain.model.ParsedReceipt
import init.peit.domain.model.ParsedReceiptItem
import init.peit.domain.service.HistoricalAttributeInheritanceService
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeParseException
import java.util.UUID
import kotlin.math.abs

data class ReceiptVerificationUiState(
    val merchant: String = "",
    val date: String = "",
    val currency: String = "USD",
    val items: List<ParsedReceiptItem> = emptyList(),
    val discount: Double = 0.0,
    val tax: Double = 0.0,
    val fee: Double = 0.0,
    val deposit: Double = 0.0,
    val paidTotal: Double = 0.0,
    val storeTier: String = "C",
    val storeRating: Double = 3.0,
    val labelsReviewed: Boolean = false,
    val isLoading: Boolean = false,
    val isSaving: Boolean = false,
    val isSaved: Boolean = false,
    val saveSuccessEventPending: Boolean = false,
    val savedLedgerEntries: List<LedgerEntity> = emptyList(),
    val errorMessage: String? = null,
    val warningMessage: String? = null
) {
    val itemsSum: Double get() = items.sumOf { it.linePrice }
    val calculatedTotal: Double
        get() = runCatching {
            ReceiptMoneyAllocator.expectedPaidTotal(items, discount, tax, fee, deposit).toDouble()
        }.getOrDefault(Double.NaN)
    val absPaidTotal: Double get() = abs(paidTotal)
    val discrepancy: Double get() = calculatedTotal - absPaidTotal
    val isBalanced: Boolean
        get() = runCatching {
            ReceiptMoneyAllocator.expectedPaidTotal(items, discount, tax, fee, deposit)
                .compareTo(ReceiptMoneyAllocator.money(abs(paidTotal))) == 0
        }.getOrDefault(false)
    val canSave: Boolean
        get() = !isLoading && !isSaving && !isSaved && ReceiptVerificationValidator.validate(this) == null
    val saveDisabledReason: String?
        get() = when {
            isLoading -> "Loading historical receipt attributes"
            isSaving -> "Saving receipt atomically"
            isSaved -> null
            else -> ReceiptVerificationValidator.validate(this)
        }
}

class ReceiptVerificationViewModel(
    private val receiptRepository: ReceiptRepository,
    private val historicalAttributeInheritanceService: HistoricalAttributeInheritanceService
) : ViewModel() {

    private val _uiState = MutableStateFlow(ReceiptVerificationUiState())
    val uiState: StateFlow<ReceiptVerificationUiState> = _uiState.asStateFlow()
    private val saveLock = Any()
    private var loadJob: Job? = null

    fun loadParsedReceipt(parsedReceipt: ParsedReceipt) {
        loadJob?.cancel()
        _uiState.value = ReceiptVerificationUiState(
            merchant = parsedReceipt.merchant,
            date = parsedReceipt.date,
            currency = parsedReceipt.currency,
            items = parsedReceipt.items,
            discount = abs(parsedReceipt.discount),
            tax = -abs(parsedReceipt.tax),
            fee = -abs(parsedReceipt.fee),
            deposit = -abs(parsedReceipt.deposit),
            paidTotal = parsedReceipt.paidTotal,
            storeTier = parsedReceipt.storeTier,
            storeRating = parsedReceipt.storeRating,
            isLoading = true,
            warningMessage = null
        )
        loadJob = viewModelScope.launch {
            try {
                val inheritedReceipt = historicalAttributeInheritanceService.inheritAttributes(parsedReceipt)
                _uiState.update { current ->
                    current.copy(
                        merchant = inheritedReceipt.merchant,
                        date = inheritedReceipt.date,
                        currency = inheritedReceipt.currency,
                        items = inheritedReceipt.items,
                        discount = abs(inheritedReceipt.discount),
                        tax = -abs(inheritedReceipt.tax),
                        fee = -abs(inheritedReceipt.fee),
                        deposit = -abs(inheritedReceipt.deposit),
                        paidTotal = inheritedReceipt.paidTotal,
                        storeTier = inheritedReceipt.storeTier,
                        storeRating = inheritedReceipt.storeRating,
                        isLoading = false
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        warningMessage = "Historical attributes could not be loaded. Review this receipt without inherited attributes. ${error.localizedMessage.orEmpty()}"
                    )
                }
            }
        }
    }

    fun updateMerchant(merchant: String) = edit { copy(merchant = merchant) }
    fun updateDate(date: String) = edit { copy(date = date) }
    fun updateCurrency(currency: String) = edit { copy(currency = currency) }
    fun updateDiscount(discount: Double) = edit { copy(discount = discount) }
    fun updateTax(tax: Double) = edit { copy(tax = tax) }
    fun updateFee(fee: Double) = edit { copy(fee = fee) }
    fun updateDeposit(deposit: Double) = edit { copy(deposit = deposit) }
    fun updatePaidTotal(paidTotal: Double) = edit { copy(paidTotal = paidTotal) }
    fun updateStoreTier(storeTier: String) = edit { copy(storeTier = storeTier) }
    fun updateStoreRating(storeRating: Double) = edit { copy(storeRating = storeRating) }
    fun markLabelsReviewed(reviewed: Boolean) = edit { copy(labelsReviewed = reviewed) }

    fun updateItem(index: Int, updatedItem: ParsedReceiptItem) {
        _uiState.update { current ->
            if (!current.isSaving && !current.isSaved && index in current.items.indices) {
                current.copy(
                    items = current.items.toMutableList().also { it[index] = updatedItem },
                    errorMessage = null
                )
            } else current
        }
    }

    fun addItem(item: ParsedReceiptItem) {
        _uiState.update { current ->
            if (current.isSaving || current.isSaved) current
            else current.copy(items = current.items + item, errorMessage = null)
        }
    }

    fun removeItem(index: Int) {
        _uiState.update { current ->
            if (!current.isSaving && !current.isSaved && index in current.items.indices) {
                current.copy(
                    items = current.items.toMutableList().also { it.removeAt(index) },
                    errorMessage = null
                )
            } else current
        }
    }

    fun consumeSaveSuccess() {
        _uiState.update { it.copy(saveSuccessEventPending = false) }
    }

    fun saveReceiptAndLedger() {
        val state = synchronized(saveLock) {
            val current = _uiState.value
            if (current.isLoading || current.isSaving || current.isSaved) return

            val validationError = ReceiptVerificationValidator.validate(current)
            if (validationError != null) {
                _uiState.value = current.copy(errorMessage = validationError)
                return
            }
            _uiState.value = current.copy(isSaving = true, errorMessage = null)
            current
        }

        viewModelScope.launch {
            try {
                val allocations = ReceiptMoneyAllocator.allocate(
                    state.items,
                    state.discount,
                    state.tax,
                    state.fee,
                    state.deposit,
                    state.paidTotal
                )
                val receiptGroupKey = UUID.randomUUID().toString()
                val receipts = state.items.mapIndexed { index, item ->
                    val allocation = allocations[index]
                    ReceiptEntity(
                        receiptId = UUID.randomUUID().toString(),
                        receiptDate = state.date,
                        merchant = state.merchant.trim(),
                        item = item.itemName.trim(),
                        brand = item.brand.trim(),
                        category = item.category.trim(),
                        quantity = item.quantity,
                        packSize = item.packSize.trim(),
                        unit = item.unit.trim(),
                        unitPrice = ReceiptMoneyAllocator.money(item.unitPrice).toDouble(),
                        currency = state.currency,
                        discount = allocation.discount.toDouble(),
                        fee = allocation.fee.toDouble(),
                        tax = allocation.tax.toDouble(),
                        deposit = allocation.deposit.toDouble(),
                        paidTotal = allocation.paidTotal.toDouble(),
                        eventType = "one_off",
                        storeTier = state.storeTier,
                        storeRating = state.storeRating,
                        brandTier = item.brandTier,
                        brandRating = item.brandRating,
                        productTier = item.productTier,
                        productRating = item.productRating,
                        availability = "in_stock",
                        notes = "Analyst labels reviewed by user; ReceiptGroup:$receiptGroupKey"
                    )
                }
                val savedLedgers = receiptRepository.addReceiptsWithLedger(receipts)
                check(savedLedgers.size == receipts.size) {
                    "Atomic receipt batch returned ${savedLedgers.size} ledger entries for ${receipts.size} items"
                }
                _uiState.update {
                    it.copy(
                        isSaving = false,
                        isSaved = true,
                        saveSuccessEventPending = true,
                        savedLedgerEntries = savedLedgers
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                _uiState.update {
                    it.copy(
                        isSaving = false,
                        errorMessage = "Failed to save receipt: ${error.localizedMessage.orEmpty()}"
                    )
                }
            }
        }
    }

    private inline fun edit(crossinline transform: ReceiptVerificationUiState.() -> ReceiptVerificationUiState) {
        _uiState.update { current ->
            if (current.isSaving || current.isSaved) current
            else transform(current).copy(errorMessage = null)
        }
    }
}

object ReceiptVerificationValidator {
    private val validCurrencies = setOf("MXN", "USD", "EUR")
    private val validTiers = setOf("A", "B", "C", "D")

    fun validate(state: ReceiptVerificationUiState): String? {
        if (state.merchant.isBlank()) return "Merchant name cannot be empty"
        if (state.date.isBlank()) return "Receipt date is required"
        try {
            LocalDate.parse(state.date)
        } catch (_: DateTimeParseException) {
            return "Enter a valid receipt date in YYYY-MM-DD format"
        }
        if (state.currency !in validCurrencies) return "Choose MXN, USD, or EUR"
        if (state.items.isEmpty()) return "Add at least one receipt item"
        if (!state.labelsReviewed) return "Review and confirm the provisional analyst labels before saving"
        if (!validTier(state.storeTier)) return "Store tier must be A, B, C, or D"
        if (!validRating(state.storeRating)) return "Store rating must be between 1 and 5"
        for ((index, item) in state.items.withIndex()) {
            val prefix = "Item ${index + 1}"
            if (item.itemName.isBlank()) return "$prefix needs a name"
            if (item.quantity <= 0.0 || !item.quantity.isFinite()) return "$prefix quantity must be positive"
            if (item.unitPrice < 0.0 || !item.unitPrice.isFinite()) return "$prefix unit price must be non-negative"
            if (item.linePrice < 0.0 || !item.linePrice.isFinite()) return "$prefix line total must be non-negative"
            if (item.packSize.isBlank() || item.unit.isBlank()) return "$prefix needs a pack size and unit"
            if (!validTier(item.brandTier) || !validTier(item.productTier)) {
                return "$prefix brand and product tiers must be A, B, C, or D"
            }
            if (!validRating(item.brandRating) || !validRating(item.productRating)) {
                return "$prefix brand and product ratings must be between 1 and 5"
            }
        }
        if (!state.paidTotal.isFinite() || state.paidTotal == 0.0) return "Observed paid total must be a finite non-zero amount"
        return try {
            ReceiptMoneyAllocator.allocate(
                state.items,
                state.discount,
                state.tax,
                state.fee,
                state.deposit,
                state.paidTotal
            )
            null
        } catch (error: IllegalArgumentException) {
            error.message ?: "Receipt totals are invalid"
        }
    }

    private fun validTier(tier: String): Boolean = tier in validTiers
    private fun validRating(rating: Double): Boolean = rating.isFinite() && rating in 1.0..5.0
}
