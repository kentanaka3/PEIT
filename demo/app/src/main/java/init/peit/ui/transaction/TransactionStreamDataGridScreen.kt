package init.peit.ui.transaction

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.TableChart
import androidx.compose.material.icons.filled.ViewAgenda
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.util.LedgerHasher

private val GRID_MIN_WIDTH = 912.dp
private const val GRID_SPLIT_MIN_WIDTH_DP = 840

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TransactionStreamDataGridScreen(
    viewModel: TransactionViewModel,
    modifier: Modifier = Modifier
) {
    var showInspectorSheet by remember { mutableStateOf(false) }

    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
        val isWideScreen = maxWidth >= 600.dp && LocalDensity.current.fontScale <= 1.3f
        LaunchedEffect(isWideScreen) {
            viewModel.setAutoViewMode(isWideScreen)
        }

        val uiState by viewModel.uiState.collectAsStateWithLifecycle()
        val snackbarHostState = remember { SnackbarHostState() }

        LaunchedEffect(uiState.userMessage) {
            uiState.userMessage?.let { msg ->
                snackbarHostState.showSnackbar(msg)
                viewModel.clearUserMessage()
            }
        }

        Box(modifier = Modifier.fillMaxSize()) {
            Column(modifier = Modifier.fillMaxSize()) {
                TransactionFilterAndHeaderBar(
                    uiState = uiState,
                    onViewModeToggle = { viewModel.toggleViewMode() },
                    onSearchQueryChange = { viewModel.setSearchQuery(it) },
                    onCategorySelect = { viewModel.setCategoryFilter(it) }
                )

                if (uiState.viewMode == ViewMode.CARD_STREAM) {
                    CardStreamView(
                        uiState = uiState,
                        onConfirm = { viewModel.confirmTransaction(it) },
                        onDiscard = { viewModel.discardTransaction(it) }
                    )
                } else {
                    FinancialDataGridView(
                        uiState = uiState,
                        onToggleSelect = { viewModel.toggleSelection(it) },
                        onToggleSelectAll = { viewModel.toggleSelectAll() },
                        onSelectItem = {
                            viewModel.selectItemForInspector(it)
                            showInspectorSheet = true
                        },
                        onBatchCategoryChange = { viewModel.batchUpdateCategory(it) },
                        onBatchStoreTierChange = { viewModel.batchUpdateStoreTier(it) },
                        onBatchConfirm = { viewModel.batchConfirmSelected() },
                        onBatchDelete = { viewModel.batchDeleteSelected() },
                        onUpdateDetail = { viewModel.updateReceiptDetail(it) }
                    )
                }
            }

            SnackbarHost(
                hostState = snackbarHostState,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(16.dp)
            )

            if (
                uiState.viewMode == ViewMode.FINANCIAL_DATA_GRID &&
                showInspectorSheet &&
                !isWideScreenForInspector(maxWidth, LocalDensity.current.fontScale)
            ) {
                uiState.selectedItem?.let { selected ->
                    ModalBottomSheet(onDismissRequest = { showInspectorSheet = false }) {
                        InspectorSheetPane(
                            itemState = selected,
                            onUpdateDetail = { viewModel.updateReceiptDetail(it) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = maxHeight * 0.9f)
                        )
                    }
                }
            }
        }
    }
}

private fun isWideScreenForInspector(width: androidx.compose.ui.unit.Dp, fontScale: Float): Boolean =
    width >= GRID_SPLIT_MIN_WIDTH_DP.dp && fontScale <= 1.15f

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TransactionFilterAndHeaderBar(
    uiState: TransactionStreamUiState,
    onViewModeToggle: () -> Unit,
    onSearchQueryChange: (String) -> Unit,
    onCategorySelect: (String) -> Unit
) {
    Surface(
        tonalElevation = 1.dp,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    modifier = Modifier.weight(1f),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = if (uiState.viewMode == ViewMode.CARD_STREAM) Icons.Default.ViewAgenda else Icons.Default.TableChart,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Transactions",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                IconButton(
                    onClick = onViewModeToggle,
                    modifier = Modifier.testTag("toggle-view-mode")
                ) {
                    Icon(
                        imageVector = if (uiState.viewMode == ViewMode.CARD_STREAM) Icons.Default.TableChart else Icons.Default.ViewAgenda,
                        contentDescription = if (uiState.viewMode == ViewMode.CARD_STREAM) {
                            "Switch to Grid view"
                        } else {
                            "Switch to Stream view"
                        }
                    )
                }
            }

            Text(
                text = if (uiState.viewMode == ViewMode.CARD_STREAM) "Stream" else "Grid",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 32.dp)
            )

            Spacer(modifier = Modifier.height(6.dp))

            OutlinedTextField(
                value = uiState.searchQuery,
                onValueChange = onSearchQueryChange,
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Search transactions or items", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                shape = RoundedCornerShape(12.dp)
            )

            Spacer(modifier = Modifier.height(8.dp))

            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                items(uiState.categories) { category ->
                    FilterChip(
                        selected = uiState.selectedCategoryFilter == category,
                        onClick = { onCategorySelect(category) },
                        label = { Text(category, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                    )
                }
            }
        }
    }
}

/**
 * Card Stream View optimized for phones & one-handed thumb gestures.
 */
@Composable
private fun CardStreamView(
    uiState: TransactionStreamUiState,
    onConfirm: (ReceiptEntity) -> Unit,
    onDiscard: (ReceiptEntity) -> Unit
) {
    val items = uiState.filteredItems

    if (items.isEmpty()) {
        EmptyTransactionsMessage(
            message = if (uiState.items.isEmpty()) {
                "No transactions yet."
            } else {
                "No transactions match these filters."
            }
        )
    } else {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item { Spacer(modifier = Modifier.height(8.dp)) }

            items(items, key = { it.receipt.receiptId }) { itemState ->
                SwipeableTransactionCard(
                    itemState = itemState,
                    onConfirm = { onConfirm(itemState.receipt) },
                    onDiscard = { onDiscard(itemState.receipt) }
                )
            }

            item { Spacer(modifier = Modifier.height(32.dp)) }
        }
    }
}

@Composable
private fun EmptyTransactionsMessage(message: String) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SwipeableTransactionCard(
    itemState: TransactionItemUiState,
    onConfirm: () -> Unit,
    onDiscard: () -> Unit
) {
    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { dismissValue ->
            when (dismissValue) {
                SwipeToDismissBoxValue.StartToEnd -> {
                    if (itemState.isConfirmed) false else {
                        onConfirm()
                        true
                    }
                }
                SwipeToDismissBoxValue.EndToStart -> {
                    if (itemState.isConfirmed) false else {
                        onDiscard()
                        true
                    }
                }
                SwipeToDismissBoxValue.Settled -> false
            }
        }
    )

    SwipeToDismissBox(
        state = dismissState,
        backgroundContent = {
            val direction = dismissState.dismissDirection
            val color by animateColorAsState(
                when (direction) {
                    SwipeToDismissBoxValue.StartToEnd -> Color(0xFF2E7D32) // Green Confirm
                    SwipeToDismissBoxValue.EndToStart -> Color(0xFFC62828) // Red Discard
                    SwipeToDismissBoxValue.Settled -> Color.Transparent
                },
                label = "swipeBgColor"
            )

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(16.dp))
                    .background(color)
                    .padding(horizontal = 24.dp),
                contentAlignment = if (direction == SwipeToDismissBoxValue.StartToEnd) Alignment.CenterStart else Alignment.CenterEnd
            ) {
                if (direction == SwipeToDismissBoxValue.StartToEnd) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color.White)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Swipe Right to Confirm", color = Color.White, fontWeight = FontWeight.Bold)
                    }
                } else if (direction == SwipeToDismissBoxValue.EndToStart) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Swipe Left to Discard", color = Color.White, fontWeight = FontWeight.Bold)
                        Spacer(modifier = Modifier.width(8.dp))
                        Icon(Icons.Default.Delete, contentDescription = null, tint = Color.White)
                    }
                }
            }
        },
        content = {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (itemState.isConfirmed)
                        MaterialTheme.colorScheme.surfaceVariant
                    else MaterialTheme.colorScheme.surfaceContainerHigh
                )
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    // Recorded state and receipt date
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        if (itemState.isConfirmed) {
                            AssistChip(
                                onClick = { },
                                label = { Text("Recorded in local hash chain") },
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.CheckCircle,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            )
                        }
                        Text(
                            text = itemState.receipt.receiptDate,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            softWrap = false
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Merchant & Item Title
                    Text(
                        text = itemState.receipt.merchant.ifBlank { "Unknown Merchant" },
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        text = itemState.receipt.item.ifBlank { "Unspecified Item" },
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    // Price & Category Details (Monospace numeric alignment)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Category: ${itemState.receipt.category.ifBlank { "General" }}",
                                style = MaterialTheme.typography.bodyMedium,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                            if (itemState.receipt.storeTier.isNotBlank()) {
                                Text(
                                    text = "Store: ${itemState.receipt.storeTier}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                        }

                        Text(
                            text = "$${"%.2f".format(itemState.receipt.paidTotal)}",
                            modifier = Modifier.widthIn(min = 88.dp),
                            style = MaterialTheme.typography.titleLarge,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.ExtraBold,
                            color = MaterialTheme.colorScheme.primary,
                            maxLines = 1,
                            softWrap = false
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // Thumb-accessible Action Buttons
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedButton(
                            onClick = onDiscard,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            enabled = !itemState.isConfirmed,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 10.dp)
                        ) {
                            Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Discard", maxLines = 1, softWrap = false)
                        }

                        Button(
                            onClick = onConfirm,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            enabled = !itemState.isConfirmed,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 10.dp)
                        ) {
                            Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = if (itemState.isConfirmed) "Recorded" else "Confirm",
                                maxLines = 1,
                                softWrap = false
                            )
                        }
                    }
                }
            }
        }
    )
}

/**
 * Financial Data Grid View for Tablet/Foldable screens.
 */
@Composable
private fun FinancialDataGridView(
    uiState: TransactionStreamUiState,
    onToggleSelect: (String) -> Unit,
    onToggleSelectAll: () -> Unit,
    onSelectItem: (String) -> Unit,
    onBatchCategoryChange: (String) -> Unit,
    onBatchStoreTierChange: (String) -> Unit,
    onBatchConfirm: () -> Unit,
    onBatchDelete: () -> Unit,
    onUpdateDetail: (ReceiptEntity) -> Unit
) {
    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val fontScale = LocalDensity.current.fontScale
        val tableWidth = maxWidth * 0.64f
        val inspectorWidth = maxWidth - tableWidth
        val splitInspector = isWideScreenForInspector(maxWidth, fontScale) &&
            tableWidth - 16.dp >= 520.dp &&
            inspectorWidth >= 300.dp

        if (splitInspector) {
            Row(modifier = Modifier.fillMaxSize()) {
                GridTablePane(
                    uiState = uiState,
                    onToggleSelect = onToggleSelect,
                    onToggleSelectAll = onToggleSelectAll,
                    onSelectItem = onSelectItem,
                    onBatchCategoryChange = onBatchCategoryChange,
                    onBatchStoreTierChange = onBatchStoreTierChange,
                    onBatchConfirm = onBatchConfirm,
                    onBatchDelete = onBatchDelete,
                    modifier = Modifier
                        .weight(0.64f)
                        .fillMaxHeight()
                )

                uiState.selectedItem?.let { selected ->
                    Surface(
                        tonalElevation = 3.dp,
                        modifier = Modifier
                            .weight(0.36f)
                            .fillMaxHeight()
                            .padding(vertical = 8.dp)
                    ) {
                        InspectorSheetPane(
                            itemState = selected,
                            onUpdateDetail = onUpdateDetail
                        )
                    }
                }
            }
        } else {
            GridTablePane(
                uiState = uiState,
                onToggleSelect = onToggleSelect,
                onToggleSelectAll = onToggleSelectAll,
                onSelectItem = onSelectItem,
                onBatchCategoryChange = onBatchCategoryChange,
                onBatchStoreTierChange = onBatchStoreTierChange,
                onBatchConfirm = onBatchConfirm,
                onBatchDelete = onBatchDelete,
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}

@Composable
private fun GridTablePane(
    uiState: TransactionStreamUiState,
    onToggleSelect: (String) -> Unit,
    onToggleSelectAll: () -> Unit,
    onSelectItem: (String) -> Unit,
    onBatchCategoryChange: (String) -> Unit,
    onBatchStoreTierChange: (String) -> Unit,
    onBatchConfirm: () -> Unit,
    onBatchDelete: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .padding(horizontal = 8.dp, vertical = 8.dp)
    ) {
        BatchActionToolbar(
            uiState = uiState,
            onToggleSelectAll = onToggleSelectAll,
            onBatchCategoryChange = onBatchCategoryChange,
            onBatchStoreTierChange = onBatchStoreTierChange,
            onBatchConfirm = onBatchConfirm,
            onBatchDelete = onBatchDelete
        )

        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Confirmed receipts cannot be deleted or have identity fields changed. Category and store-tier edits are labels outside the identity hash.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(8.dp))

        if (uiState.filteredItems.isEmpty()) {
            EmptyTransactionsMessage(
                message = if (uiState.items.isEmpty()) {
                    "No transactions yet."
                } else {
                    "No transactions match these filters."
                }
            )
        } else {
            BoxWithConstraints(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
            ) {
                val contentWidth = maxOf(maxWidth, GRID_MIN_WIDTH)
                Column(
                    modifier = Modifier
                        .horizontalScroll(rememberScrollState())
                        .width(contentWidth)
                ) {
                    DataGridHeaderRow()
                    Spacer(modifier = Modifier.height(4.dp))
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        items(uiState.filteredItems, key = { it.receipt.receiptId }) { itemState ->
                            DataGridRow(
                                itemState = itemState,
                                isInspectorSelected = uiState.selectedItem?.receipt?.receiptId == itemState.receipt.receiptId,
                                onToggleSelect = { onToggleSelect(itemState.receipt.receiptId) },
                                onRowClick = { onSelectItem(itemState.receipt.receiptId) }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun BatchActionToolbar(
    uiState: TransactionStreamUiState,
    onToggleSelectAll: () -> Unit,
    onBatchCategoryChange: (String) -> Unit,
    onBatchStoreTierChange: (String) -> Unit,
    onBatchConfirm: () -> Unit,
    onBatchDelete: () -> Unit
) {
    var categoryMenuExpanded by remember { mutableStateOf(false) }
    var storeTierMenuExpanded by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(
            modifier = Modifier
                .padding(8.dp)
                .fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(
                    checked = uiState.filteredItems.isNotEmpty() && uiState.filteredItems.all { it.isSelected },
                    onCheckedChange = { onToggleSelectAll() }
                )
                Text(
                    text = "${uiState.selectedCount} Selected",
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(modifier = Modifier.weight(1f)) {
                    OutlinedButton(
                        onClick = { categoryMenuExpanded = true },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("batch-category-button"),
                        enabled = uiState.selectedCount > 0,
                        shape = RoundedCornerShape(8.dp),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 8.dp)
                    ) {
                        Text(
                            text = "Category",
                            modifier = Modifier.testTag("batch-category-label"),
                            maxLines = 1,
                            softWrap = false
                        )
                    }
                    DropdownMenu(
                        expanded = categoryMenuExpanded,
                        onDismissRequest = { categoryMenuExpanded = false }
                    ) {
                        listOf("Groceries", "Utilities", "Transportation", "Health & Beauty", "Electronics", "General").forEach { cat ->
                            DropdownMenuItem(
                                text = { Text(cat) },
                                onClick = {
                                    onBatchCategoryChange(cat)
                                    categoryMenuExpanded = false
                                }
                            )
                        }
                    }
                }

                Box(modifier = Modifier.weight(1f)) {
                    OutlinedButton(
                        onClick = { storeTierMenuExpanded = true },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("batch-tier-button"),
                        enabled = uiState.selectedCount > 0,
                        shape = RoundedCornerShape(8.dp),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 8.dp)
                    ) {
                        Text(
                            text = "Store tier",
                            modifier = Modifier.testTag("batch-tier-label"),
                            maxLines = 1,
                            softWrap = false
                        )
                    }
                    DropdownMenu(
                        expanded = storeTierMenuExpanded,
                        onDismissRequest = { storeTierMenuExpanded = false }
                    ) {
                        listOf("A", "B", "C", "D", "E").forEach { tier ->
                            DropdownMenuItem(
                                text = { Text(tier) },
                                onClick = {
                                    onBatchStoreTierChange(tier)
                                    storeTierMenuExpanded = false
                                }
                            )
                        }
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onBatchConfirm,
                    modifier = Modifier
                        .weight(1f)
                        .testTag("batch-confirm-button"),
                    enabled = uiState.selectedCount > 0,
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 8.dp)
                ) {
                    Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "Confirm",
                        modifier = Modifier.testTag("batch-confirm-label"),
                        maxLines = 1,
                        softWrap = false
                    )
                }

                OutlinedButton(
                    onClick = onBatchDelete,
                    modifier = Modifier
                        .weight(1f)
                        .testTag("batch-delete-button"),
                    enabled = uiState.selectedCount > 0,
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 8.dp)
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "Delete",
                        modifier = Modifier.testTag("batch-delete-label"),
                        maxLines = 1,
                        softWrap = false
                    )
                }
            }
        }
    }
}

@Composable
private fun DataGridHeaderRow() {
    Surface(
        color = MaterialTheme.colorScheme.primaryContainer,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .width(GRID_MIN_WIDTH)
                .padding(horizontal = 8.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Spacer(modifier = Modifier.width(52.dp))
            GridHeaderCell("Item", 204.dp, "grid-heading-item")
            GridHeaderCell("Category", 132.dp, "grid-heading-category")
            GridHeaderCell("Merchant", 164.dp, "grid-heading-merchant")
            GridHeaderCell("Date", 120.dp, "grid-heading-date")
            GridHeaderCell("Paid total", 112.dp, "grid-heading-total")
            GridHeaderCell("Status", 108.dp, "grid-heading-status")
        }
    }
}

@Composable
private fun GridHeaderCell(label: String, width: androidx.compose.ui.unit.Dp, tag: String) {
    Text(
        text = label,
        modifier = Modifier
            .width(width)
            .testTag(tag),
        fontWeight = FontWeight.Bold,
        style = MaterialTheme.typography.bodySmall,
        maxLines = 1,
        softWrap = false,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
private fun DataGridRow(
    itemState: TransactionItemUiState,
    isInspectorSelected: Boolean,
    onToggleSelect: () -> Unit,
    onRowClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onRowClick() },
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isInspectorSelected)
                MaterialTheme.colorScheme.secondaryContainer
            else if (itemState.isSelected)
                MaterialTheme.colorScheme.surfaceVariant
            else
                MaterialTheme.colorScheme.surface
        )
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Checkbox(
                checked = itemState.isSelected,
                onCheckedChange = { onToggleSelect() },
                modifier = Modifier.size(48.dp)
            )

            Text(
                text = itemState.receipt.item.ifBlank { "Unspecified Item" },
                modifier = Modifier.width(204.dp),
                fontWeight = FontWeight.SemiBold,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )

            Text(
                text = itemState.receipt.category.ifBlank { "General" },
                modifier = Modifier.width(132.dp),
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            Text(
                text = itemState.receipt.merchant.ifBlank { "Unknown" },
                modifier = Modifier.width(164.dp),
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            Text(
                text = itemState.receipt.receiptDate,
                modifier = Modifier.width(120.dp),
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
                maxLines = 1,
                softWrap = false
            )

            Text(
                text = "$${"%.2f".format(itemState.receipt.paidTotal)}",
                modifier = Modifier.width(112.dp),
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.bodyMedium,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.primary,
                maxLines = 1,
                softWrap = false
            )

            Text(
                text = if (itemState.isConfirmed) "Recorded" else "Pending",
                modifier = Modifier.width(108.dp),
                style = MaterialTheme.typography.bodySmall,
                color = if (itemState.isConfirmed) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                softWrap = false
            )
        }
    }
}

/**
 * Split Inspector Sheet Pane displaying cropper snippet preview & metadata live editing.
 */
@Composable
private fun InspectorSheetPane(
    itemState: TransactionItemUiState,
    onUpdateDetail: (ReceiptEntity) -> Unit,
    modifier: Modifier = Modifier
) {
    var merchant by remember(itemState) { mutableStateOf(itemState.receipt.merchant) }
    var item by remember(itemState) { mutableStateOf(itemState.receipt.item) }
    var category by remember(itemState) { mutableStateOf(itemState.receipt.category) }
    var unitPrice by remember(itemState) { mutableStateOf(itemState.receipt.unitPrice.toString()) }
    var quantity by remember(itemState) { mutableStateOf(itemState.receipt.quantity.toString()) }
    var paidTotal by remember(itemState) { mutableStateOf(itemState.receipt.paidTotal.toString()) }
    var storeTier by remember(itemState) { mutableStateOf(itemState.receipt.storeTier) }
    var notes by remember(itemState) { mutableStateOf(itemState.receipt.notes) }

    val entryHash = remember(itemState.receipt, itemState.ledgerEntryId) {
        itemState.ledgerEntryId ?: LedgerHasher.computeEntryId(itemState.receipt)
    }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Receipt details",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                AssistChip(
                    onClick = { },
                    label = { Text(if (itemState.isConfirmed) "Recorded" else "Pending") },
                    leadingIcon = {
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = if (itemState.isConfirmed) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline
                        )
                    }
                )
            }
        }

        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
            ) {
                Column(
                    modifier = Modifier
                        .padding(16.dp)
                        .fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "Receipt image",
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "No receipt image is attached to this transaction.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        // Ledger Entry Hash Card
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp)
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(
                        text = if (itemState.isConfirmed) "Stored ledger identity hash:" else "Proposed canonical identity hash (not yet recorded):",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Text(
                        text = entryHash,
                        style = MaterialTheme.typography.bodySmall,
                        fontFamily = FontFamily.Monospace,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }

        item {
            Text(
                text = "This identity hash covers receipt ID, item, paid total (formatted to six decimals), and date only. Merchant, category, store tier, notes, quantity, and unit price are not committed by it. Merchant/category/store-tier/notes label edits are allowed. Confirmed identity fields are locked; quantity and unit price are also locked here after confirmation but are not hashed. The chain is a consistency check, not a signature or full-record tamper evidence.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        // Editable Details Fields
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = merchant,
                    onValueChange = { merchant = it },
                    label = { Text("Merchant") },
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = item,
                    onValueChange = { item = it },
                    label = { Text("Item Name") },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !itemState.isConfirmed
                )

                OutlinedTextField(
                    value = category,
                    onValueChange = { category = it },
                    label = { Text("Category") },
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = storeTier,
                    onValueChange = { storeTier = it },
                    label = { Text("Store Tier") },
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = unitPrice,
                    onValueChange = { unitPrice = it },
                    label = { Text("Unit Price") },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !itemState.isConfirmed
                )

                OutlinedTextField(
                    value = quantity,
                    onValueChange = { quantity = it },
                    label = { Text("Quantity") },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !itemState.isConfirmed
                )

                OutlinedTextField(
                    value = paidTotal,
                    onValueChange = { paidTotal = it },
                    label = { Text("Paid Total") },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !itemState.isConfirmed
                )

                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("Notes / Tags") },
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(8.dp))

                Button(
                    onClick = {
                        val updated = itemState.receipt.copy(
                            merchant = merchant,
                            item = item,
                            category = category,
                            unitPrice = unitPrice.toDoubleOrNull() ?: itemState.receipt.unitPrice,
                            quantity = quantity.toDoubleOrNull() ?: itemState.receipt.quantity,
                            paidTotal = paidTotal.toDoubleOrNull() ?: itemState.receipt.paidTotal,
                            storeTier = storeTier,
                            notes = notes
                        )
                        onUpdateDetail(updated)
                    },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Default.Edit, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Save changes", maxLines = 1, softWrap = false)
                }
            }
        }
    }
}
