package init.peit.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ShowChart
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.TableChart
import androidx.compose.material.icons.filled.Verified
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSerializable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.serialization.NavBackStackSerializer
import init.peit.domain.model.ParsedReceipt
import init.peit.ui.capture.ReceiptCaptureScreen
import init.peit.ui.econometric.EconometricDashboardScreen
import init.peit.ui.econometric.EconometricDashboardViewModel
import init.peit.ui.ledger.LedgerAuditLogScreen
import init.peit.ui.ledger.LedgerAuditLogViewModel
import init.peit.ui.transaction.TransactionStreamDataGridScreen
import init.peit.ui.transaction.TransactionViewModel
import init.peit.ui.verification.ReceiptVerificationScreen
import init.peit.ui.verification.ReceiptVerificationViewModel

data class NavTabItem(
    val route: NavRoute,
    val title: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScaffold(
    transactionViewModel: TransactionViewModel,
    verificationViewModel: ReceiptVerificationViewModel,
    econometricViewModel: EconometricDashboardViewModel,
    ledgerViewModel: LedgerAuditLogViewModel,
    modifier: Modifier = Modifier
) {
    val backStack = rememberSerializable(
        serializer = NavBackStackSerializer(NavRoute.serializer())
    ) {
        NavBackStack<NavRoute>(NavRoute.TransactionStream)
    }
    val currentRoute = backStack.lastOrNull() ?: NavRoute.TransactionStream

    var activeParsedReceipt by remember { mutableStateOf<ParsedReceipt?>(null) }

    val tabs = remember {
        listOf(
            NavTabItem(NavRoute.TransactionStream, "Receipts", Icons.Default.TableChart),
            NavTabItem(NavRoute.ReceiptCapture, "Capture", Icons.Default.CameraAlt),
            NavTabItem(NavRoute.VerificationHud, "Review", Icons.Default.Verified),
            NavTabItem(NavRoute.EconometricDashboard, "Prices", Icons.AutoMirrored.Filled.ShowChart),
            NavTabItem(NavRoute.LedgerAuditLog, "Audit", Icons.Default.Security)
        )
    }

    val navigateToTab: (NavRoute) -> Unit = { route ->
        if (backStack.lastOrNull() != route) {
            backStack.add(route)
        }
    }

    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
        val isWideScreen = maxWidth >= 600.dp
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            topBar = {
                TopAppBar(
                    title = {
                        androidx.compose.foundation.layout.Column {
                            Text(
                                text = "PEIT",
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.titleMedium
                            )
                            Text(
                                text = "Synthetic demo · local receipt ledger",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surface
                    )
                )
            },
            bottomBar = {
                if (!isWideScreen) {
                    PeitNavigationBar(
                        tabs = tabs,
                        currentRoute = currentRoute,
                        onSelect = navigateToTab
                    )
                }
            }
        ) { innerPadding ->
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
            ) {
                if (isWideScreen) {
                    NavigationRail {
                        tabs.forEach { tab ->
                            val selected = currentRoute == tab.route
                            NavigationRailItem(
                                selected = selected,
                                onClick = { navigateToTab(tab.route) },
                                icon = { Icon(tab.icon, contentDescription = tab.title) },
                                label = { NavigationLabel(tab) }
                            )
                        }
                    }
                }

                Box(modifier = Modifier.weight(1f)) {
                    AppNavigation(
                        backStack = backStack,
                        onBack = {
                            if (backStack.size > 1) {
                                backStack.removeAt(backStack.lastIndex)
                            }
                        }
                    ) { route ->
                        when (route) {
                            NavRoute.TransactionStream -> {
                                TransactionStreamDataGridScreen(viewModel = transactionViewModel)
                            }
                            NavRoute.ReceiptCapture -> {
                                ReceiptCaptureScreen(
                                    onReceiptParsed = { parsed ->
                                        activeParsedReceipt = parsed
                                        navigateToTab(NavRoute.VerificationHud)
                                    }
                                )
                            }
                            NavRoute.VerificationHud -> {
                                ReceiptVerificationScreen(
                                    viewModel = verificationViewModel,
                                    initialParsedReceipt = activeParsedReceipt,
                                    onSaveSuccess = {
                                        activeParsedReceipt = null
                                        navigateToTab(NavRoute.TransactionStream)
                                    }
                                )
                            }
                            NavRoute.EconometricDashboard -> {
                                EconometricDashboardScreen(viewModel = econometricViewModel)
                            }
                            NavRoute.LedgerAuditLog -> {
                                LedgerAuditLogScreen(viewModel = ledgerViewModel)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
internal fun PeitNavigationBar(
    tabs: List<NavTabItem>,
    currentRoute: NavRoute,
    onSelect: (NavRoute) -> Unit,
    modifier: Modifier = Modifier
) {
    NavigationBar(modifier = modifier) {
        tabs.forEach { tab ->
            NavigationBarItem(
                selected = currentRoute == tab.route,
                onClick = { onSelect(tab.route) },
                icon = { Icon(tab.icon, contentDescription = null) },
                label = { NavigationLabel(tab) }
            )
        }
    }
}

@Composable
private fun NavigationLabel(tab: NavTabItem) {
    Text(
        text = tab.title,
        modifier = Modifier.testTag("navigation-${tab.title.lowercase()}"),
        maxLines = 1,
        softWrap = false,
        overflow = TextOverflow.Ellipsis,
        style = MaterialTheme.typography.labelSmall
    )
}
