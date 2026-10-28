package init.peit.ui.ledger

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import init.peit.data.local.entity.LedgerEntity
import init.peit.data.repository.ReceiptRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class LedgerAuditLogUiState(
    val entries: List<LedgerEntity> = emptyList(),
    val isIntegrityValid: Boolean = true,
    val isVerifying: Boolean = false,
    val selectedEntry: LedgerEntity? = null,
    val userMessage: String? = null
)

class LedgerAuditLogViewModel(
    private val receiptRepository: ReceiptRepository
) : ViewModel() {

    private val _entriesFlow = receiptRepository.getAllLedgerEntries()
    private val _isIntegrityValid = MutableStateFlow(true)
    private val _isVerifying = MutableStateFlow(false)
    private val _selectedEntry = MutableStateFlow<LedgerEntity?>(null)
    private val _userMessage = MutableStateFlow<String?>(null)

    val uiState: StateFlow<LedgerAuditLogUiState> = combine(
        _entriesFlow,
        _isIntegrityValid,
        _isVerifying,
        _selectedEntry,
        _userMessage
    ) { entries, isValid, isVerifying, selected, msg ->
        LedgerAuditLogUiState(
            entries = entries,
            isIntegrityValid = isValid,
            isVerifying = isVerifying,
            selectedEntry = selected,
            userMessage = msg
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = LedgerAuditLogUiState()
    )

    init {
        verifyLedgerIntegrity()
    }

    fun verifyLedgerIntegrity() {
        viewModelScope.launch {
            _isVerifying.value = true
            try {
                val isValid = receiptRepository.verifyLedgerIntegrity()
                _isIntegrityValid.value = isValid
                _userMessage.value = if (isValid)
                    "Stored receipt identity hashes and predecessor links are consistent."
                else
                    "Warning: stored receipt identity hashes or predecessor links are inconsistent."
            } catch (e: Exception) {
                _isIntegrityValid.value = false
                _userMessage.value = "Verification error: ${e.message}"
            } finally {
                _isVerifying.value = false
            }
        }
    }

    fun selectEntry(entry: LedgerEntity) {
        _selectedEntry.value = entry
    }

    fun clearUserMessage() {
        _userMessage.value = null
    }
}
