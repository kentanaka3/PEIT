package init.peit

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import init.peit.data.local.database.AppDatabase
import init.peit.data.local.database.DatabaseSeeder
import init.peit.data.repository.EconometricRepositoryImpl
import init.peit.data.repository.ReceiptRepositoryImpl
import init.peit.domain.service.HistoricalAttributeInheritanceService
import init.peit.ui.econometric.EconometricDashboardViewModel
import init.peit.ui.ledger.LedgerAuditLogViewModel
import init.peit.ui.navigation.MainScaffold
import init.peit.ui.theme.PEITTheme
import init.peit.ui.transaction.TransactionViewModel
import init.peit.ui.verification.ReceiptVerificationViewModel
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val database = AppDatabase.getInstance(applicationContext)
        val receiptRepository = ReceiptRepositoryImpl(database)
        val econometricRepository = EconometricRepositoryImpl(receiptRepository)
        val historicalService = HistoricalAttributeInheritanceService(receiptRepository)

        lifecycleScope.launch {
            DatabaseSeeder.seedIfEmpty(receiptRepository)
        }

        val factory = viewModelFactory {
            initializer { TransactionViewModel(receiptRepository) }
            initializer { ReceiptVerificationViewModel(receiptRepository, historicalService) }
            initializer { EconometricDashboardViewModel(econometricRepository) }
            initializer { LedgerAuditLogViewModel(receiptRepository) }
        }
        val provider = ViewModelProvider(this, factory)
        val transactionViewModel = provider[TransactionViewModel::class.java]
        val verificationViewModel = provider[ReceiptVerificationViewModel::class.java]
        val econometricViewModel = provider[EconometricDashboardViewModel::class.java]
        val ledgerViewModel = provider[LedgerAuditLogViewModel::class.java]

        setContent {
            PEITTheme {
                MainScaffold(
                    transactionViewModel = transactionViewModel,
                    verificationViewModel = verificationViewModel,
                    econometricViewModel = econometricViewModel,
                    ledgerViewModel = ledgerViewModel
                )
            }
        }
    }
}
