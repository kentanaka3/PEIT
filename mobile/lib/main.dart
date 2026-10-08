import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'controllers/receipt_review_controller.dart';
import 'data/database.dart';
import 'ocr/models.dart';
import 'screens/dashboard_screen.dart';
import 'screens/home_screen.dart';
import 'screens/receipt_card_stream_screen.dart';
import 'services/pairing_service.dart';
import 'services/secure_storage_service.dart';
import 'services/sync_service.dart';
import 'web_interop.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Web Interop Bridge
  WebInteropService().initBridge();

  // Initialize SQLite database (in-memory fallback on web or test environments)
  AppDatabase db;
  try {
    if (kIsWeb) {
      db = AppDatabase.openInMemory();
    } else {
      db = await AppDatabase.openDefault();
    }
  } catch (_) {
    db = AppDatabase.openInMemory();
  }

  // Initialize Secure Storage and Pairing Service
  final secureStorage = SecureStorageService();
  final pairingService = PairingService(secureStorage: secureStorage);

  // Initialize Sync Service targeting desktop daemon (default localhost:8000)
  final syncService = SyncService(
    baseUrl: 'http://127.0.0.1:8000',
    database: db,
    secureStorage: secureStorage,
  );

  runApp(PeitApp(
    database: db,
    syncService: syncService,
    secureStorage: secureStorage,
    pairingService: pairingService,
  ));
}

/// Root widget for the PEIT Mobile application with Material 3 styling
/// and embedded island routing support (?island=card_stream | ?island=dashboard).
class PeitApp extends StatelessWidget {
  final AppDatabase database;
  final SyncService syncService;
  final SecureStorageService secureStorage;
  final PairingService pairingService;
  final String? initialIsland;

  const PeitApp({
    super.key,
    required this.database,
    required this.syncService,
    required this.secureStorage,
    required this.pairingService,
    this.initialIsland,
  });

  Widget _buildIslandRoute(String? islandParam) {
    if (islandParam == 'receipt_card_stream' || islandParam == 'card_stream') {
      // Create review controller for embedded receipt stream mode
      final controller = ReceiptReviewController(
        receiptId: 'rcpt-island-sample',
        receiptDate: DateTime.now().toIso8601String().substring(0, 10),
        merchant: 'Soriana Hiper (Island)',
        currency: 'MXN',
        detectedPaidTotal: 142.50,
        initialItems: [
          ParsedLineItem(
            item: 'LECHE CLASICA 1L',
            totalPrice: 28.50,
            unitPrice: 28.50,
            category: 'Groceries',
            confidence: 0.98,
          ),
          ParsedLineItem(
            item: 'PAN BLANCO ARTESANAL',
            totalPrice: 48.00,
            unitPrice: 48.00,
            category: 'Bakery',
            confidence: 0.96,
          ),
          ParsedLineItem(
            item: 'MANZANA GALA 1.2KG',
            totalPrice: 66.00,
            unitPrice: 55.00,
            quantity: 1.2,
            unit: 'kg',
            category: 'Produce',
            confidence: 0.91,
          ),
        ],
      );
      WebInteropService().notifyReady('receipt_card_stream');
      return ReceiptCardStreamScreen(
        controller: controller,
        database: database,
      );
    } else if (islandParam == 'dashboard') {
      WebInteropService().notifyReady('dashboard');
      return DashboardScreen(database: database);
    }

    return HomeScreen(
      database: database,
      syncService: syncService,
      secureStorage: secureStorage,
      pairingService: pairingService,
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PEIT Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E88E5), // PEIT brand blue
          brightness: Brightness.light,
        ),
        appBarTheme: const AppBarTheme(
          centerTitle: false,
          elevation: 0,
        ),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E88E5),
          brightness: Brightness.dark,
        ),
      ),
      themeMode: ThemeMode.system,
      onGenerateRoute: (settings) {
        final uri = Uri.tryParse(settings.name ?? '/');
        final islandParam = initialIsland ?? uri?.queryParameters['island'];
        return MaterialPageRoute(
          builder: (_) => _buildIslandRoute(islandParam),
        );
      },
    );
  }
}
