package init.peit.ui.verification

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.util.Locale
import kotlin.math.abs

@Composable
fun StickyBalanceVerificationHud(
    uiState: ReceiptVerificationUiState,
    onSaveAndConfirm: () -> Unit,
    modifier: Modifier = Modifier
) {
    val symbol = when (uiState.currency.uppercase(Locale.ROOT)) {
        "MXN" -> "MXN $"
        "EUR" -> "€"
        else -> "USD $"
    }
    val statusContainer by animateColorAsState(
        targetValue = if (uiState.isBalanced) {
            MaterialTheme.colorScheme.primaryContainer
        } else {
            MaterialTheme.colorScheme.errorContainer
        },
        label = "balanceStatusContainer"
    )
    val statusContent = if (uiState.isBalanced) {
        MaterialTheme.colorScheme.onPrimaryContainer
    } else {
        MaterialTheme.colorScheme.onErrorContainer
    }

    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
        tonalElevation = 8.dp,
        shadowElevation = 12.dp
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 360.dp)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = statusContainer,
                    contentColor = statusContent
                )
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Icon(
                            imageVector = if (uiState.isBalanced) {
                                Icons.Default.CheckCircle
                            } else {
                                Icons.Default.Warning
                            },
                            contentDescription = null,
                            tint = statusContent
                        )
                        Text(
                            text = if (uiState.isBalanced) "Receipt balances" else "Balance discrepancy",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Text(
                        text = if (uiState.isBalanced) {
                            "Calculated total matches the observed payment."
                        } else {
                            "Resolve the difference before saving. No amount is adjusted automatically."
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = statusContent
                    )
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                            BalanceAmount(
                                label = "Calculated",
                                value = uiState.calculatedTotal,
                                symbol = symbol,
                                modifier = Modifier.weight(1f)
                            )
                            BalanceAmount(
                                label = "Observed paid",
                                value = uiState.absPaidTotal,
                                symbol = symbol,
                                modifier = Modifier.weight(1f)
                            )
                        }
                        BalanceAmount(
                            label = "Difference",
                            value = uiState.discrepancy,
                            symbol = symbol,
                            signed = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                Text(
                    text = "Total breakdown",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    text = "Items ${money(uiState.itemsSum, symbol)} − discount ${money(uiState.discount, symbol)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = " + charges ${money(abs(uiState.tax) + abs(uiState.fee) + abs(uiState.deposit), symbol)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Button(
                onClick = onSaveAndConfirm,
                enabled = uiState.canSave,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 52.dp)
                    .testTag("review-save-button"),
                shape = RoundedCornerShape(14.dp)
            ) {
                when {
                    uiState.isLoading -> {
                        CircularProgressIndicator(
                            color = MaterialTheme.colorScheme.onPrimary,
                            modifier = Modifier.padding(end = 8.dp)
                        )
                        Text("Loading receipt history…")
                    }
                    uiState.isSaving -> {
                        CircularProgressIndicator(
                            color = MaterialTheme.colorScheme.onPrimary,
                            modifier = Modifier.padding(end = 8.dp)
                        )
                        Text("Saving receipt…")
                    }
                    uiState.isSaved -> {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 8.dp)
                        )
                        Text("Receipt saved")
                    }
                    else -> {
                        Icon(
                            imageVector = Icons.Default.Lock,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 8.dp)
                        )
                        Text(
                            text = if (uiState.isBalanced) "Review & save receipt" else "Resolve balance to save",
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            uiState.errorMessage?.let { message ->
                FeedbackMessage(message, isWarning = true)
            }
            uiState.warningMessage?.let { message ->
                FeedbackMessage(message, isWarning = true)
            }
            uiState.saveDisabledReason?.let { reason ->
                if (!uiState.isSaving) FeedbackMessage(reason, isWarning = true)
            }
        }
    }
}

@Composable
private fun BalanceAmount(
    label: String,
    value: Double,
    symbol: String,
    modifier: Modifier = Modifier,
    signed: Boolean = false
) {
    Column(modifier = modifier) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = money(value, symbol, signed),
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold
        )
    }
}

@Composable
private fun FeedbackMessage(message: String, isWarning: Boolean) {
    Text(
        text = message,
        color = if (isWarning) MaterialTheme.colorScheme.error else Color.Unspecified,
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp)
    )
}

private fun money(value: Double, symbol: String, signed: Boolean = false): String {
    val sign = if (signed && value > 0.0) "+" else if (signed && value < 0.0) "−" else ""
    return "$sign$symbol${String.format(Locale.US, "%.2f", abs(value))}"
}
