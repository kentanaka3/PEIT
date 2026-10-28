package init.peit.ui.navigation

import kotlinx.serialization.Serializable
import androidx.navigation3.runtime.NavKey

@Serializable
sealed interface NavRoute : NavKey {
    @Serializable
    data object TransactionStream : NavRoute

    @Serializable
    data object ReceiptCapture : NavRoute

    @Serializable
    data object VerificationHud : NavRoute

    @Serializable
    data object EconometricDashboard : NavRoute

    @Serializable
    data object LedgerAuditLog : NavRoute
}
