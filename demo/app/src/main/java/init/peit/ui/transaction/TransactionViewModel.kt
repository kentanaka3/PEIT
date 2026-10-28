package init.peit.ui.transaction

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.ReceiptRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class ViewMode {
    CARD_STREAM,
    FINANCIAL_DATA_GRID
}

data class TransactionItemUiState(
    val receipt: ReceiptEntity,
    val isConfirmed: Boolean,
    val ledgerEntryId: String? = null,
    val isSelected: Boolean = false
)

data class TransactionStreamUiState(
    val items: List<TransactionItemUiState> = emptyList(),
    val selectedItem: TransactionItemUiState? = null,
    val viewMode: ViewMode = ViewMode.CARD_STREAM,
    val searchQuery: String = "",
    val selectedCategoryFilter: String = "All",
    val isProcessingBatch: Boolean = false,
    val userOverrodeViewMode: Boolean = false,
    val userMessage: String? = null
) {
    val selectedCount: Int get() = items.count { it.isSelected }
    val categories: List<String> get() = listOf("All") + items.map { it.receipt.category.ifBlank { "General" } }.distinct()
    val filteredItems: List<TransactionItemUiState>
        get() = items.filter { item ->
            val matchesCategory = selectedCategoryFilter == "All" || item.receipt.category.ifBlank { "General" } == selectedCategoryFilter
            val matchesSearch = searchQuery.isBlank() ||
                    item.receipt.merchant.contains(searchQuery, ignoreCase = true) ||
                    item.receipt.item.contains(searchQuery, ignoreCase = true) ||
                    item.receipt.category.contains(searchQuery, ignoreCase = true)
            matchesCategory && matchesSearch
        }
}

private data class ControlState(
    val selectedItemKey: String?,
    val viewMode: ViewMode,
    val searchQuery: String,
    val categoryFilter: String
)

private data class MetaState(
    val userOverrodeViewMode: Boolean,
    val userMessage: String?
)

class TransactionViewModel(
    private val receiptRepository: ReceiptRepository
) : ViewModel() {

    private val _rawReceipts = receiptRepository.getAllReceipts()
    private val _ledgerEntries = receiptRepository.getAllLedgerEntries()

    private val _selectedIds = MutableStateFlow<Set<String>>(emptySet())
    private val _selectedItemKey = MutableStateFlow<String?>(null)
    private val _viewMode = MutableStateFlow(ViewMode.CARD_STREAM)
    private val _userOverrodeViewMode = MutableStateFlow(false)
    private val _searchQuery = MutableStateFlow("")
    private val _categoryFilter = MutableStateFlow("All")
    private val _userMessage = MutableStateFlow<String?>(null)

    private val _itemsFlow = combine(_rawReceipts, _ledgerEntries, _selectedIds) { rawReceipts, ledgerEntries, selectedIds ->
        val ledgerByReceiptId = ledgerEntries.associateBy { it.receiptId }
        rawReceipts.map { receipt ->
            val ledgerEntry = ledgerByReceiptId[receipt.receiptId]
            TransactionItemUiState(
                receipt = receipt,
                isConfirmed = ledgerEntry != null,
                ledgerEntryId = ledgerEntry?.entryId,
                isSelected = selectedIds.contains(receipt.receiptId)
            )
        }
    }

    private val _controlStateFlow = combine(_selectedItemKey, _viewMode, _searchQuery, _categoryFilter) { key, mode, query, cat ->
        ControlState(key, mode, query, cat)
    }

    private val _metaStateFlow = combine(_userOverrodeViewMode, _userMessage) { overrode, msg ->
        MetaState(overrode, msg)
    }

    val uiState: StateFlow<TransactionStreamUiState> = combine(
        _itemsFlow,
        _controlStateFlow,
        _metaStateFlow
    ) { items, control, meta ->
        val currentSelected = items.firstOrNull { it.receipt.receiptId == control.selectedItemKey }
            ?: items.firstOrNull()

        TransactionStreamUiState(
            items = items,
            selectedItem = currentSelected,
            viewMode = control.viewMode,
            searchQuery = control.searchQuery,
            selectedCategoryFilter = control.categoryFilter,
            userOverrodeViewMode = meta.userOverrodeViewMode,
            userMessage = meta.userMessage
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = TransactionStreamUiState()
    )

    fun setAutoViewMode(isWideScreen: Boolean) {
        if (!_userOverrodeViewMode.value) {
            _viewMode.value = if (isWideScreen) ViewMode.FINANCIAL_DATA_GRID else ViewMode.CARD_STREAM
        }
    }

    fun toggleViewMode() {
        _userOverrodeViewMode.value = true
        _viewMode.update { current ->
            if (current == ViewMode.CARD_STREAM) ViewMode.FINANCIAL_DATA_GRID else ViewMode.CARD_STREAM
        }
    }

    fun setSearchQuery(query: String) {
        _searchQuery.value = query
    }

    fun setCategoryFilter(category: String) {
        _categoryFilter.value = category
    }

    fun selectItemForInspector(receiptId: String) {
        _selectedItemKey.value = receiptId
    }

    fun toggleSelection(receiptId: String) {
        _selectedIds.update { set ->
            if (set.contains(receiptId)) set - receiptId else set + receiptId
        }
    }

    fun toggleSelectAll() {
        val currentItems = uiState.value.filteredItems
        val allSelected = currentItems.all { it.isSelected }
        if (allSelected) {
            _selectedIds.value = emptySet()
        } else {
            _selectedIds.value = currentItems.map { it.receipt.receiptId }.toSet()
        }
    }

    fun confirmTransaction(receipt: ReceiptEntity) {
        viewModelScope.launch {
            try {
                receiptRepository.addReceiptWithLedger(receipt)
                _userMessage.value = "Transaction recorded in the local hash chain."
            } catch (e: Exception) {
                _userMessage.value = "Error confirming transaction: ${e.message}"
            }
        }
    }

    fun discardTransaction(receipt: ReceiptEntity) {
        viewModelScope.launch {
            try {
                receiptRepository.deleteReceiptById(receipt.receiptId)
                _userMessage.value = "Transaction discarded."
            } catch (e: Exception) {
                _userMessage.value = "Error discarding transaction: ${e.message}"
            }
        }
    }

    fun batchUpdateCategory(newCategory: String) {
        val selectedIds = _selectedIds.value
        if (selectedIds.isEmpty()) return

        viewModelScope.launch {
            val currentItems = uiState.value.items.filter { selectedIds.contains(it.receipt.receiptId) }
            for (item in currentItems) {
                val updated = item.receipt.copy(category = newCategory)
                receiptRepository.updateReceipt(updated)
            }
            _userMessage.value = "Updated category to '$newCategory' for ${selectedIds.size} items."
            _selectedIds.value = emptySet()
        }
    }

    fun batchUpdateStoreTier(newStoreTier: String) {
        val selectedIds = _selectedIds.value
        if (selectedIds.isEmpty()) return

        viewModelScope.launch {
            val currentItems = uiState.value.items.filter { selectedIds.contains(it.receipt.receiptId) }
            for (item in currentItems) {
                val updated = item.receipt.copy(storeTier = newStoreTier)
                receiptRepository.updateReceipt(updated)
            }
            _userMessage.value = "Updated store tier to '$newStoreTier' for ${selectedIds.size} items."
            _selectedIds.value = emptySet()
        }
    }

    fun batchConfirmSelected() {
        val selectedIds = _selectedIds.value
        if (selectedIds.isEmpty()) return

        viewModelScope.launch {
            val currentItems = uiState.value.items.filter { selectedIds.contains(it.receipt.receiptId) }
            val pendingReceipts = currentItems.filterNot { it.isConfirmed }.map { it.receipt }
            try {
                receiptRepository.addReceiptsWithLedger(pendingReceipts)
                _userMessage.value = "Recorded ${pendingReceipts.size} selected transactions in the local hash chain."
            } catch (e: Exception) {
                _userMessage.value = "Error recording selected transactions: ${e.message}"
            }
            _selectedIds.value = emptySet()
        }
    }

    fun batchDeleteSelected() {
        val selectedIds = _selectedIds.value
        if (selectedIds.isEmpty()) return

        viewModelScope.launch {
            val pendingItems = uiState.value.items
                .filter { selectedIds.contains(it.receipt.receiptId) && !it.isConfirmed }
            try {
                for (item in pendingItems) {
                    receiptRepository.deleteReceiptById(item.receipt.receiptId)
                }
                val skippedCount = selectedIds.size - pendingItems.size
                _userMessage.value = if (skippedCount == 0) {
                    "Deleted ${pendingItems.size} pending transactions."
                } else {
                    "Deleted ${pendingItems.size} pending transactions; kept $skippedCount confirmed receipts."
                }
            } catch (e: Exception) {
                _userMessage.value = "Error deleting pending transactions: ${e.message}"
            }
            _selectedIds.value = emptySet()
        }
    }

    fun updateReceiptDetail(receipt: ReceiptEntity) {
        viewModelScope.launch {
            try {
                receiptRepository.updateReceipt(receipt)
                _userMessage.value =
                    "Receipt labels updated. Merchant, category, store tier, and notes are not committed by the identity hash."
            } catch (e: Exception) {
                _userMessage.value = "Receipt update rejected: ${e.message}"
            }
        }
    }

    fun clearUserMessage() {
        _userMessage.value = null
    }
}
