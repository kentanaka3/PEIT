package init.peit.ui.verification

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Receipt
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.unit.dp
import init.peit.domain.model.ParsedReceipt
import init.peit.domain.model.ParsedReceiptItem

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReceiptVerificationScreen(
    viewModel: ReceiptVerificationViewModel,
    initialParsedReceipt: ParsedReceipt?,
    onSaveSuccess: () -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(initialParsedReceipt) {
        if (initialParsedReceipt != null) {
            viewModel.loadParsedReceipt(initialParsedReceipt)
        }
    }

    LaunchedEffect(uiState.saveSuccessEventPending) {
        if (uiState.saveSuccessEventPending) {
            viewModel.consumeSaveSuccess()
            onSaveSuccess()
        }
    }

    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
        val compact = maxWidth < 600.dp
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            topBar = {
                TopAppBar(
                    title = {
                        Text(
                            text = "Review receipt",
                            maxLines = 1
                        )
                    }
                )
            },
            bottomBar = {
                StickyBalanceVerificationHud(
                    uiState = uiState,
                    onSaveAndConfirm = { viewModel.saveReceiptAndLedger() }
                )
            }
        ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Receipt Metadata Section
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "Merchant & Date",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        if (compact) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = uiState.merchant,
                                onValueChange = { viewModel.updateMerchant(it) },
                                label = { Text("Merchant") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            OutlinedTextField(
                                value = uiState.date,
                                onValueChange = { viewModel.updateDate(it) },
                                label = { Text("Date (YYYY-MM-DD; required)") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            }
                        } else {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                OutlinedTextField(
                                    value = uiState.merchant,
                                    onValueChange = { viewModel.updateMerchant(it) },
                                    label = { Text("Merchant") },
                                    modifier = Modifier.weight(1f)
                                )
                                OutlinedTextField(
                                    value = uiState.date,
                                    onValueChange = { viewModel.updateDate(it) },
                                    label = { Text("Date (YYYY-MM-DD; required)") },
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        Text("Currency Selection", style = MaterialTheme.typography.bodyMedium)
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.padding(top = 4.dp)
                        ) {
                            listOf("MXN", "USD", "EUR").forEach { curr ->
                                FilterChip(
                                    selected = uiState.currency == curr,
                                    onClick = { viewModel.updateCurrency(curr) },
                                    label = { Text(curr) }
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Text("Store analyst labels", style = MaterialTheme.typography.bodyMedium)
                        if (compact) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = uiState.storeTier,
                                    onValueChange = { viewModel.updateStoreTier(it.uppercase()) },
                                    label = { Text("Store tier (A–D)") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = uiState.storeRating.toString(),
                                    onValueChange = { it.toDoubleOrNull()?.let(viewModel::updateStoreRating) },
                                    label = { Text("Store rating (1–5)") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        } else {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = uiState.storeTier,
                                onValueChange = { viewModel.updateStoreTier(it.uppercase()) },
                                label = { Text("Store tier (A–D)") },
                                modifier = Modifier.weight(1f)
                            )
                            OutlinedTextField(
                                value = uiState.storeRating.toString(),
                                onValueChange = { it.toDoubleOrNull()?.let(viewModel::updateStoreRating) },
                                label = { Text("Store rating (1–5)") },
                                modifier = Modifier.weight(1f)
                            )
                            }
                        }
                        Text(
                            "C / 3.0 values are provisional analyst defaults, not observations.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            // Line Items Section Header
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Line Items (${uiState.items.size})",
                        style = MaterialTheme.typography.titleLarge
                    )
                    OutlinedButton(
                        onClick = {
                            viewModel.addItem(
                                ParsedReceiptItem(
                                    itemName = "New Item",
                                    quantity = 1.0,
                                    unitPrice = 0.0,
                                    linePrice = 0.0
                                )
                            )
                        }
                    ) {
                        Icon(Icons.Default.Add, contentDescription = null)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Add Item")
                    }
                }
            }

            // Items List
            itemsIndexed(uiState.items) { index, item ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            // Cropped snippet thumbnail preview if available
                            if (item.croppedSnippetBitmap != null) {
                                Image(
                                    bitmap = item.croppedSnippetBitmap.asImageBitmap(),
                                    contentDescription = "OCR Snippet",
                                    modifier = Modifier
                                        .size(60.dp, 36.dp)
                                        .padding(end = 8.dp)
                                )
                            } else {
                                Icon(
                                    imageVector = Icons.Default.Receipt,
                                    contentDescription = null,
                                    modifier = Modifier.padding(end = 8.dp)
                                )
                            }

                            OutlinedTextField(
                                value = item.itemName,
                                onValueChange = {
                                    viewModel.updateItem(index, item.copy(itemName = it))
                                },
                                label = { Text("Item Name") },
                                modifier = Modifier.weight(1f)
                            )

                            IconButton(onClick = { viewModel.removeItem(index) }) {
                                Icon(Icons.Default.Delete, contentDescription = "Delete item")
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        if (compact) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = item.quantity.toString(),
                                    onValueChange = { v ->
                                        v.toDoubleOrNull()?.let { q ->
                                            viewModel.updateItem(index, item.copy(quantity = q, linePrice = q * item.unitPrice))
                                        }
                                    },
                                    label = { Text("Quantity") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = item.unitPrice.toString(),
                                    onValueChange = { v ->
                                        v.toDoubleOrNull()?.let { p ->
                                            viewModel.updateItem(index, item.copy(unitPrice = p, linePrice = item.quantity * p))
                                        }
                                    },
                                    label = { Text("Unit price") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = item.linePrice.toString(),
                                    onValueChange = { v ->
                                        v.toDoubleOrNull()?.let { lp ->
                                            viewModel.updateItem(index, item.copy(linePrice = lp))
                                        }
                                    },
                                    label = { Text("Line total") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        } else {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                            OutlinedTextField(
                                value = item.quantity.toString(),
                                onValueChange = { v ->
                                    v.toDoubleOrNull()?.let { q ->
                                        viewModel.updateItem(index, item.copy(quantity = q, linePrice = q * item.unitPrice))
                                    }
                                },
                                label = { Text("Qty") },
                                modifier = Modifier.weight(1f)
                            )

                            OutlinedTextField(
                                value = item.unitPrice.toString(),
                                onValueChange = { v ->
                                    v.toDoubleOrNull()?.let { p ->
                                        viewModel.updateItem(index, item.copy(unitPrice = p, linePrice = item.quantity * p))
                                    }
                                },
                                label = { Text("Unit Price") },
                                modifier = Modifier.weight(1f)
                            )

                            OutlinedTextField(
                                value = item.linePrice.toString(),
                                onValueChange = { v ->
                                    v.toDoubleOrNull()?.let { lp ->
                                        viewModel.updateItem(index, item.copy(linePrice = lp))
                                    }
                                },
                                label = { Text("Line Total") },
                                modifier = Modifier.weight(1f)
                            )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        if (compact) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = item.packSize,
                                    onValueChange = { viewModel.updateItem(index, item.copy(packSize = it)) },
                                    label = { Text("Pack size") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = item.category,
                                    onValueChange = { viewModel.updateItem(index, item.copy(category = it)) },
                                    label = { Text("Category") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        } else {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                            OutlinedTextField(
                                value = item.packSize,
                                onValueChange = { viewModel.updateItem(index, item.copy(packSize = it)) },
                                label = { Text("Pack Size") },
                                modifier = Modifier.weight(1f)
                            )
                            OutlinedTextField(
                                value = item.category,
                                onValueChange = { viewModel.updateItem(index, item.copy(category = it)) },
                                label = { Text("Category") },
                                modifier = Modifier.weight(1f)
                            )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Text("Brand and product analyst labels (tiers A–D; ratings 1–5)", style = MaterialTheme.typography.bodySmall)
                        if (compact) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = item.brandTier,
                                    onValueChange = { viewModel.updateItem(index, item.copy(brandTier = it.uppercase())) },
                                    label = { Text("Brand tier") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = item.productTier,
                                    onValueChange = { viewModel.updateItem(index, item.copy(productTier = it.uppercase())) },
                                    label = { Text("Product tier") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        } else {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = item.brandTier,
                                onValueChange = { viewModel.updateItem(index, item.copy(brandTier = it.uppercase())) },
                                label = { Text("Brand tier") },
                                modifier = Modifier.weight(1f)
                            )
                            OutlinedTextField(
                                value = item.productTier,
                                onValueChange = { viewModel.updateItem(index, item.copy(productTier = it.uppercase())) },
                                label = { Text("Product tier") },
                                modifier = Modifier.weight(1f)
                            )
                            }
                        }
                        if (compact) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = item.brandRating.toString(),
                                    onValueChange = { it.toDoubleOrNull()?.let { rating -> viewModel.updateItem(index, item.copy(brandRating = rating)) } },
                                    label = { Text("Brand rating") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = item.productRating.toString(),
                                    onValueChange = { it.toDoubleOrNull()?.let { rating -> viewModel.updateItem(index, item.copy(productRating = rating)) } },
                                    label = { Text("Product rating") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        } else {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = item.brandRating.toString(),
                                onValueChange = { it.toDoubleOrNull()?.let { rating -> viewModel.updateItem(index, item.copy(brandRating = rating)) } },
                                label = { Text("Brand rating") },
                                modifier = Modifier.weight(1f)
                            )
                            OutlinedTextField(
                                value = item.productRating.toString(),
                                onValueChange = { it.toDoubleOrNull()?.let { rating -> viewModel.updateItem(index, item.copy(productRating = rating)) } },
                                label = { Text("Product rating") },
                                modifier = Modifier.weight(1f)
                            )
                            }
                        }
                    }
                }
            }

            // Summary Totals Breakdown (Tax, Discount, Fee, Deposit, Paid Total)
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Totals & Adjustments", style = MaterialTheme.typography.titleMedium)

                        Spacer(modifier = Modifier.height(8.dp))

                        if (compact) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(
                                    value = uiState.discount.toString(),
                                    onValueChange = { it.toDoubleOrNull()?.let { d -> viewModel.updateDiscount(d) } },
                                    label = { Text("Discount (-)") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = uiState.tax.toString(),
                                    onValueChange = { it.toDoubleOrNull()?.let { t -> viewModel.updateTax(t) } },
                                    label = { Text("Tax (stored ≤ 0)") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = uiState.fee.toString(),
                                    onValueChange = { it.toDoubleOrNull()?.let { f -> viewModel.updateFee(f) } },
                                    label = { Text("Fee (stored ≤ 0)") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                                OutlinedTextField(
                                    value = uiState.deposit.toString(),
                                    onValueChange = { it.toDoubleOrNull()?.let { dep -> viewModel.updateDeposit(dep) } },
                                    label = { Text("Deposit (stored ≤ 0)") },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        } else {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                            OutlinedTextField(
                                value = uiState.discount.toString(),
                                onValueChange = { it.toDoubleOrNull()?.let { d -> viewModel.updateDiscount(d) } },
                                label = { Text("Discount (-)") },
                                modifier = Modifier.weight(1f)
                            )
                            OutlinedTextField(
                                value = uiState.tax.toString(),
                                onValueChange = { it.toDoubleOrNull()?.let { t -> viewModel.updateTax(t) } },
                                label = { Text("Tax (stored ≤ 0)") },
                                modifier = Modifier.weight(1f)
                            )
                            }
                        }

                        if (!compact) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                            OutlinedTextField(
                                value = uiState.fee.toString(),
                                onValueChange = { it.toDoubleOrNull()?.let { f -> viewModel.updateFee(f) } },
                                label = { Text("Fee (stored ≤ 0)") },
                                modifier = Modifier.weight(1f)
                            )
                            OutlinedTextField(
                                value = uiState.deposit.toString(),
                                onValueChange = { it.toDoubleOrNull()?.let { dep -> viewModel.updateDeposit(dep) } },
                                label = { Text("Deposit (stored ≤ 0)") },
                                modifier = Modifier.weight(1f)
                            )
                            }
                        }
                        Spacer(modifier = Modifier.height(8.dp))

                        OutlinedTextField(
                            value = uiState.paidTotal.toString(),
                            onValueChange = { it.toDoubleOrNull()?.let { pt -> viewModel.updatePaidTotal(pt) } },
                            label = { Text("Observed Paid Total") },
                            modifier = Modifier.fillMaxWidth()
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Checkbox(
                                checked = uiState.labelsReviewed,
                                onCheckedChange = viewModel::markLabelsReviewed
                            )
                            Text(
                                text = "I reviewed the provisional / inherited analyst labels.",
                                modifier = Modifier.weight(1f),
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                    }
                }
            }

            item {
                Spacer(modifier = Modifier.height(32.dp))
            }
        }
    }
}
