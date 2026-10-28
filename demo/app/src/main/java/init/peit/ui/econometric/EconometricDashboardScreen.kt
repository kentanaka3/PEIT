package init.peit.ui.econometric

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import init.peit.domain.model.InflationIndexResult
import init.peit.domain.model.IndexStatus

@Composable
fun EconometricDashboardScreen(
    viewModel: EconometricDashboardViewModel,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
    val compact = maxWidth < 600.dp
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Column {
                Text(
                    text = "Matched-item price indicator",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "For matched items, 100 × the equal-weight mean of current-to-base unit-price ratios. Period unit prices are quantity-weighted by quantity.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Period comparison", style = MaterialTheme.typography.titleMedium)
                    if (compact) {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            FilterChip(
                                modifier = Modifier.fillMaxWidth(),
                                selected = uiState.comparisonMode == PeriodComparisonMode.MONTH_OVER_MONTH,
                                onClick = {
                                    viewModel.setComparisonMode(PeriodComparisonMode.MONTH_OVER_MONTH)
                                },
                                label = { Text("Previous month") }
                            )
                            FilterChip(
                                modifier = Modifier.fillMaxWidth(),
                                selected = uiState.comparisonMode == PeriodComparisonMode.YEAR_OVER_YEAR,
                                onClick = {
                                    viewModel.setComparisonMode(PeriodComparisonMode.YEAR_OVER_YEAR)
                                },
                                label = { Text("Previous year") }
                            )
                            FilterChip(
                                modifier = Modifier.fillMaxWidth(),
                                selected = uiState.comparisonMode == PeriodComparisonMode.CUSTOM_BASE,
                                onClick = {
                                    viewModel.setComparisonMode(PeriodComparisonMode.CUSTOM_BASE)
                                },
                                label = { Text("Custom base period") }
                            )
                        }
                    } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = uiState.comparisonMode == PeriodComparisonMode.MONTH_OVER_MONTH,
                            onClick = {
                                viewModel.setComparisonMode(PeriodComparisonMode.MONTH_OVER_MONTH)
                            },
                            label = { Text("Previous month") }
                        )
                        FilterChip(
                            selected = uiState.comparisonMode == PeriodComparisonMode.YEAR_OVER_YEAR,
                            onClick = {
                                viewModel.setComparisonMode(PeriodComparisonMode.YEAR_OVER_YEAR)
                            },
                            label = { Text("Previous year") }
                        )
                        FilterChip(
                            selected = uiState.comparisonMode == PeriodComparisonMode.CUSTOM_BASE,
                            onClick = {
                                viewModel.setComparisonMode(PeriodComparisonMode.CUSTOM_BASE)
                            },
                            label = { Text("Custom") }
                        )
                    }
                    }
                    Text(
                        text = "Compare the current period with the selected baseline.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (compact) {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = uiState.basePeriodLabel,
                                onValueChange = viewModel::updateBasePeriod,
                                label = { Text("Base period (YYYY-MM)") },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true
                            )
                            OutlinedTextField(
                                value = uiState.currentPeriodLabel,
                                onValueChange = viewModel::updateCurrentPeriod,
                                label = { Text("Current period (YYYY-MM)") },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true
                            )
                        }
                    } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = uiState.basePeriodLabel,
                            onValueChange = viewModel::updateBasePeriod,
                            label = { Text("Base (YYYY-MM)") },
                            modifier = Modifier.weight(1f),
                            singleLine = true
                        )
                        OutlinedTextField(
                            value = uiState.currentPeriodLabel,
                            onValueChange = viewModel::updateCurrentPeriod,
                            label = { Text("Current (YYYY-MM)") },
                            modifier = Modifier.weight(1f),
                            singleLine = true
                        )
                    }
                    }
                }
                }
            }
        }

        if (uiState.isLoading) {
            item {
                CircularProgressIndicator()
            }
        }
        uiState.errorMessage?.let { message ->
            item {
                Text(
                    text = message,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }

        uiState.overallIndices?.let { indices ->
            item { OverallIndexCard(indices) }
            item {
                Text(
                    text = "Category comparisons",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            if (uiState.categoryIndices.isEmpty()) {
                item {
                    Text(
                        "No confirmed consumption categories in these periods.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            items(uiState.categoryIndices, key = { it.categoryName }) { category ->
                CategoryIndexCard(category)
            }
            if (indices.itemDetails.isNotEmpty()) {
                item {
                    Text(
                        text = "Matched item details",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
                items(indices.itemDetails, key = { it.itemKey }) { detail ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Text(detail.itemName, fontWeight = FontWeight.Bold)
                            Text(
                                text = "Unit price: ${format(detail.basePrice)} → ${format(detail.currentPrice)} ${indices.currency.orEmpty()}",
                                style = MaterialTheme.typography.bodyMedium
                            )
                            Text(
                                text = "Price relative: ${format(detail.priceRatio * 100.0)} (base = 100)",
                                style = MaterialTheme.typography.bodySmall,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OverallIndexCard(indices: InflationIndexResult) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                "${indices.basePeriod.label} → ${indices.currentPeriod.label}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            if (indices.priceIndex != null) {
                Text(
                    text = "Matched-item price index (base = 100)",
                    style = MaterialTheme.typography.bodyMedium
                )
                Text(
                    text = format(indices.priceIndex),
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = "Change: ${signed(indices.priceChangePercentage ?: 0.0)}%",
                    style = MaterialTheme.typography.titleMedium
                )
            } else {
                StatusText(indices.status)
            }
            Text(
                "Matched-item coverage: ${indices.matchedItemCount}/${indices.baseItemCount} base items (${format(indices.coveragePercent)}%)",
                style = MaterialTheme.typography.bodyMedium
            )
            if (indices.currency != null) {
                Text("Currency: ${indices.currency}", style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(4.dp))
            Text(
                text = "Expenditure comparison (separate from price change)",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold
            )
            if (indices.currency != null && indices.expenditure != null) {
                Text("Current confirmed expenditure: ${format(indices.expenditure)} ${indices.currency}")
            }
            if (indices.expenditureIndex != null) {
                Text(
                    "Index: ${format(indices.expenditureIndex)} (base = 100) · Change: ${signed(indices.expenditureChangePercentage ?: 0.0)}%"
                )
            } else {
                StatusText(indices.expenditureStatus)
            }
        }
    }
}

@Composable
private fun CategoryIndexCard(category: CategoryInflationUiModel) {
    val result = category.result
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(category.categoryName, style = MaterialTheme.typography.titleMedium)
            if (result.priceIndex != null) {
                Text(
                    "Index: ${format(result.priceIndex)} (base = 100) · Change: ${signed(result.priceChangePercentage ?: 0.0)}%"
                )
            } else {
                StatusText(result.status)
            }
            Text(
                "Matched-item coverage: ${result.matchedItemCount}/${result.baseItemCount} base items (${format(result.coveragePercent)}%)",
                style = MaterialTheme.typography.bodySmall
            )
            if (result.expenditureIndex == null) {
                Text(
                    "Expenditure: ${result.expenditureStatus.message}",
                    style = MaterialTheme.typography.bodySmall
                )
            } else {
                Text(
                    "Expenditure index: ${format(result.expenditureIndex)}",
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

@Composable
private fun StatusText(status: IndexStatus) {
    Text(
        text = status.message,
        color = if (status == IndexStatus.AVAILABLE) {
            MaterialTheme.colorScheme.onSurface
        } else {
            MaterialTheme.colorScheme.onSurfaceVariant
        },
        style = MaterialTheme.typography.bodyMedium
    )
}

private fun format(value: Double) = "%.2f".format(value)

private fun signed(value: Double) =
    "${if (value >= 0.0) "+" else ""}${format(value)}"
