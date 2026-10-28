package init.peit.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation3.runtime.NavEntry
import androidx.navigation3.ui.NavDisplay

@Composable
fun AppNavigation(
    backStack: List<NavRoute>,
    modifier: Modifier = Modifier,
    onBack: () -> Unit = {},
    onRouteContent: @Composable (NavRoute) -> Unit
) {
    NavDisplay(
        backStack = backStack,
        modifier = modifier,
        onBack = onBack,
        entryProvider = { route ->
            NavEntry(route) {
                onRouteContent(route)
            }
        }
    )
}
