package init.peit.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.SemanticsActions
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import init.peit.domain.model.ParsedReceiptItem
import init.peit.ui.navigation.NavTabItem
import init.peit.ui.navigation.NavRoute
import init.peit.ui.navigation.PeitNavigationBar
import init.peit.ui.theme.PEITTheme
import init.peit.ui.verification.ReceiptVerificationUiState
import init.peit.ui.verification.StickyBalanceVerificationHud
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ShowChart
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.TableChart
import androidx.compose.material.icons.filled.Verified

@RunWith(AndroidJUnit4::class)
class ResponsiveUiTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun navigationLabelsStayOnOneLineAtPhoneWidthAndLargeFont() {
        composeRule.setContent {
            val baseDensity = LocalDensity.current
            CompositionLocalProvider(
                LocalDensity provides Density(baseDensity.density, fontScale = 1.5f)
            ) {
                PEITTheme {
                    Column(Modifier.width(360.dp)) {
                        PeitNavigationBar(
                            tabs = listOf(
                                NavTabItem(NavRoute.TransactionStream, "Receipts", Icons.Default.TableChart),
                                NavTabItem(NavRoute.ReceiptCapture, "Capture", Icons.Default.CameraAlt),
                                NavTabItem(NavRoute.VerificationHud, "Review", Icons.Default.Verified),
                                NavTabItem(NavRoute.EconometricDashboard, "Prices", Icons.AutoMirrored.Filled.ShowChart),
                                NavTabItem(NavRoute.LedgerAuditLog, "Audit", Icons.Default.Security)
                            ),
                            currentRoute = NavRoute.TransactionStream,
                            onSelect = {}
                        )
                    }
                }
            }
        }

        listOf("receipts", "capture", "review", "prices", "audit").forEach { label ->
            composeRule.onNodeWithTag("navigation-$label")
                .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { results ->
                    val layout = results.single()
                    assertEquals("$label should remain one line", 1, layout.lineCount)
                    assertFalse("$label should not be clipped", layout.didOverflowWidth)
                }
        }
    }

    @Test
    fun reviewSaveActionRemainsReachableInScrollableHud() {
        composeRule.setContent {
            val baseDensity = LocalDensity.current
            CompositionLocalProvider(
                LocalDensity provides Density(baseDensity.density, fontScale = 1.5f)
            ) {
                PEITTheme {
                    Column(
                        modifier = Modifier
                            .width(360.dp)
                            .height(500.dp)
                    ) {
                        StickyBalanceVerificationHud(
                            uiState = ReceiptVerificationUiState(
                                merchant = "Market",
                                date = "2026-10-22",
                                items = listOf(
                                    ParsedReceiptItem(
                                        itemName = "Rice",
                                        quantity = 1.0,
                                        unitPrice = 12.4,
                                        linePrice = 12.4
                                    )
                                ),
                                paidTotal = 12.4,
                                labelsReviewed = true
                            ),
                            onSaveAndConfirm = {}
                        )
                    }
                }
            }
        }

        composeRule.onNodeWithText("Difference").assertIsDisplayed()
        composeRule.onNodeWithTag("review-save-button")
            .performScrollTo()
            .assertIsDisplayed()
    }
}
