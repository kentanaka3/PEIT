package init.peit.ui.transaction

import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.fetchSemanticsNode
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.lifecycle.viewModelScope
import init.peit.data.local.database.AppDatabase
import init.peit.data.local.entity.ReceiptEntity
import init.peit.data.repository.ReceiptRepositoryImpl
import init.peit.ui.theme.PEITTheme
import kotlinx.coroutines.cancel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TransactionGridLayoutTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun gridActionsAndColumnsFitAt360Dp() {
        assertGridTextFits(fontScale = 1f)
    }

    @Test
    fun gridActionsAndColumnsFitAt360DpWithLargeFontScale() {
        assertGridTextFits(fontScale = 1.5f)
    }

    private fun assertGridTextFits(fontScale: Float) {
        val context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation()
            .targetContext
        val database = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        val repository = ReceiptRepositoryImpl(database)
        runBlocking {
            repository.insertReceipts(
                listOf(
                    ReceiptEntity(
                        receiptId = "grid-layout-test",
                        receiptDate = "2026-06-12",
                        merchant = "Neighborhood Market",
                        item = "Whole grain breakfast cereal pack",
                        category = "Groceries",
                        paidTotal = -3.75
                    )
                )
            )
        }
        val viewModel = TransactionViewModel(repository)
        viewModel.toggleViewMode()

        try {
            composeRule.setContent {
                val originalDensity = LocalDensity.current
                CompositionLocalProvider(
                    LocalDensity provides Density(
                        density = originalDensity.density,
                        fontScale = fontScale
                    )
                ) {
                    PEITTheme {
                        Box(
                            modifier = androidx.compose.ui.Modifier
                                .width(360.dp)
                                .fillMaxHeight()
                        ) {
                            TransactionStreamDataGridScreen(
                                viewModel = viewModel,
                                modifier = androidx.compose.ui.Modifier.fillMaxSize()
                            )
                        }
                    }
                }
            }

            composeRule.onNodeWithContentDescription("Switch to Stream view")
                .assertIsDisplayed()
            composeRule.waitUntil(5_000) {
                composeRule.onAllNodesWithTag(
                    "grid-heading-category",
                    useUnmergedTree = true
                ).fetchSemanticsNodes().isNotEmpty()
            }

            listOf(
                "batch-category-label" to 64,
                "batch-tier-label" to 72,
                "batch-confirm-label" to 56,
                "batch-delete-label" to 48
            ).forEach { (tag, minWidthDp) ->
                composeRule.assertSingleLineWithoutOverflow(tag)
                composeRule.assertMeasuredWidthAtLeast(tag, minWidthDp)
            }

            listOf(
                "grid-heading-item" to 200,
                "grid-heading-category" to 128,
                "grid-heading-merchant" to 160,
                "grid-heading-date" to 116,
                "grid-heading-total" to 108,
                "grid-heading-status" to 104
            ).forEach { (tag, minWidthDp) ->
                composeRule.assertSingleLineWithoutOverflow(tag)
                composeRule.assertMeasuredWidthAtLeast(tag, minWidthDp)
            }
        } finally {
            composeRule.setContent { }
            composeRule.waitForIdle()
            viewModel.viewModelScope.cancel()
            database.close()
        }
    }

    private fun ComposeContentTestRule.assertSingleLineWithoutOverflow(tag: String) {
        val results = mutableListOf<TextLayoutResult>()
        onNodeWithTag(tag, useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { action ->
                assertTrue("Expected text layout for $tag", action(results))
            }
        val result = results.single()
        assertEquals("$tag should stay on one line", 1, result.lineCount)
        assertFalse("$tag should not overflow", result.hasVisualOverflow)
    }

    private fun ComposeContentTestRule.assertMeasuredWidthAtLeast(tag: String, minWidthDp: Int) {
        val measuredWidthDp = onNodeWithTag(tag, useUnmergedTree = true)
            .fetchSemanticsNode()
            .layoutInfo
            .let { with(density) { it.width.toDp().value } }
        assertTrue(
            "$tag should retain at least $minWidthDp dp; measured $measuredWidthDp dp",
            measuredWidthDp >= minWidthDp
        )
    }
}
