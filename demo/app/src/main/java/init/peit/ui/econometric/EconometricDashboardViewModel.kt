package init.peit.ui.econometric

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import init.peit.data.repository.EconometricRepository
import init.peit.domain.model.InflationIndexResult
import init.peit.domain.model.TimePeriod
import java.util.Calendar
import java.util.Locale
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.stateIn

enum class PeriodComparisonMode {
    MONTH_OVER_MONTH,
    YEAR_OVER_YEAR,
    CUSTOM_BASE
}

data class CategoryInflationUiModel(
    val categoryName: String,
    val result: InflationIndexResult
)

data class EconometricDashboardUiState(
    val comparisonMode: PeriodComparisonMode = PeriodComparisonMode.MONTH_OVER_MONTH,
    val basePeriodLabel: String = monthLabel(-1),
    val currentPeriodLabel: String = monthLabel(0),
    val overallIndices: InflationIndexResult? = null,
    val categoryIndices: List<CategoryInflationUiModel> = emptyList(),
    val isLoading: Boolean = true,
    val errorMessage: String? = null
)

private data class FilterState(
    val comparisonMode: PeriodComparisonMode,
    val basePeriodLabel: String,
    val currentPeriodLabel: String
)

private data class DataState(
    val basePeriodLabel: String,
    val currentPeriodLabel: String,
    val overallIndices: InflationIndexResult?,
    val categoryIndices: List<CategoryInflationUiModel>,
    val isLoading: Boolean,
    val errorMessage: String?
)

@OptIn(ExperimentalCoroutinesApi::class)
class EconometricDashboardViewModel(
    private val econometricRepository: EconometricRepository
) : ViewModel() {

    private val _comparisonMode = kotlinx.coroutines.flow.MutableStateFlow(
        PeriodComparisonMode.MONTH_OVER_MONTH
    )
    private val _basePeriodLabel = kotlinx.coroutines.flow.MutableStateFlow(monthLabel(-1))
    private val _currentPeriodLabel = kotlinx.coroutines.flow.MutableStateFlow(monthLabel(0))

    private val filterStateFlow = combine(
        _comparisonMode,
        _basePeriodLabel,
        _currentPeriodLabel
    ) { mode, baseLabel, currentLabel ->
        FilterState(mode, baseLabel, currentLabel)
    }

    private val dataStateFlow = filterStateFlow.flatMapLatest { filter ->
        val periods = runCatching {
            TimePeriod.ofMonth(filter.basePeriodLabel) to
                TimePeriod.ofMonth(filter.currentPeriodLabel)
        }
        val error = periods.exceptionOrNull()
        if (error != null) {
            flowOf(
                DataState(
                    basePeriodLabel = filter.basePeriodLabel,
                    currentPeriodLabel = filter.currentPeriodLabel,
                    overallIndices = null,
                    categoryIndices = emptyList(),
                    isLoading = false,
                    errorMessage = error.message ?: "Enter valid YYYY-MM periods."
                )
            )
        } else {
            val (basePeriod, currentPeriod) = periods.getOrThrow()
            econometricRepository.getIndexResultsFlow(basePeriod, currentPeriod).map { results ->
                DataState(
                    basePeriodLabel = filter.basePeriodLabel,
                    currentPeriodLabel = filter.currentPeriodLabel,
                    overallIndices = results.overall,
                    categoryIndices = results.categories.entries
                        .map { CategoryInflationUiModel(it.key, it.value) }
                        .sortedWith(
                            compareByDescending<CategoryInflationUiModel> {
                                it.result.priceChangePercentage ?: Double.NEGATIVE_INFINITY
                            }.thenBy { it.categoryName }
                        ),
                    isLoading = false,
                    errorMessage = null
                )
            }.onStart {
                emit(
                    DataState(
                        basePeriodLabel = filter.basePeriodLabel,
                        currentPeriodLabel = filter.currentPeriodLabel,
                        overallIndices = null,
                        categoryIndices = emptyList(),
                        isLoading = true,
                        errorMessage = null
                    )
                )
            }.catch { error ->
                emit(
                    DataState(
                        basePeriodLabel = filter.basePeriodLabel,
                        currentPeriodLabel = filter.currentPeriodLabel,
                        overallIndices = null,
                        categoryIndices = emptyList(),
                        isLoading = false,
                        errorMessage = error.message ?: "Unable to calculate indices."
                    )
                )
            }
        }
    }

    val uiState: StateFlow<EconometricDashboardUiState> = combine(
        filterStateFlow,
        dataStateFlow
    ) { filter, data ->
        val dataMatchesFilter =
            data.basePeriodLabel == filter.basePeriodLabel &&
                data.currentPeriodLabel == filter.currentPeriodLabel
        EconometricDashboardUiState(
            comparisonMode = filter.comparisonMode,
            basePeriodLabel = filter.basePeriodLabel,
            currentPeriodLabel = filter.currentPeriodLabel,
            overallIndices = if (dataMatchesFilter) data.overallIndices else null,
            categoryIndices = if (dataMatchesFilter) data.categoryIndices else emptyList(),
            isLoading = if (dataMatchesFilter) data.isLoading else true,
            errorMessage = if (dataMatchesFilter) data.errorMessage else null
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = EconometricDashboardUiState()
    )

    fun setComparisonMode(mode: PeriodComparisonMode) {
        _comparisonMode.value = mode
        if (mode != PeriodComparisonMode.CUSTOM_BASE) {
            val offset = if (mode == PeriodComparisonMode.MONTH_OVER_MONTH) -1 else -12
            monthOffset(_currentPeriodLabel.value, offset)?.let { _basePeriodLabel.value = it }
        }
    }

    fun updateBasePeriod(periodLabel: String) {
        _basePeriodLabel.value = periodLabel
    }

    fun updateCurrentPeriod(periodLabel: String) {
        _currentPeriodLabel.value = periodLabel
        if (_comparisonMode.value != PeriodComparisonMode.CUSTOM_BASE) {
            val offset = if (_comparisonMode.value == PeriodComparisonMode.MONTH_OVER_MONTH) -1 else -12
            monthOffset(periodLabel, offset)?.let { _basePeriodLabel.value = it }
        }
    }
}

private fun monthLabel(offset: Int): String {
    val calendar = Calendar.getInstance()
    calendar.add(Calendar.MONTH, offset)
    return String.format(
        Locale.ROOT,
        "%04d-%02d",
        calendar.get(Calendar.YEAR),
        calendar.get(Calendar.MONTH) + 1
    )
}

private fun monthOffset(label: String, offset: Int): String? {
    if (!label.matches(Regex("^\\d{4}-(0[1-9]|1[0-2])$"))) return null
    val year = label.substringBefore("-").toIntOrNull() ?: return null
    val month = label.substringAfter("-").toIntOrNull() ?: return null
    val absoluteMonth = year * 12 + month - 1 + offset
    val adjustedYear = Math.floorDiv(absoluteMonth, 12)
    val adjustedMonth = Math.floorMod(absoluteMonth, 12) + 1
    return String.format(Locale.ROOT, "%04d-%02d", adjustedYear, adjustedMonth)
}
