import 'package:flutter/material.dart';

import 'data/database.dart';
import 'screens/home_screen.dart';
import 'services/pairing_service.dart';
import 'services/secure_storage_service.dart';
import 'services/sync_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize SQLite database
  final db = await AppDatabase.openDefault();

  // Initialize Secure Storage and Pairing Service
  final secureStorage = SecureStorageService();
  final pairingService = PairingService(secureStorage: secureStorage);

  // Initialize Sync Service targeting desktop daemon (default localhost:8000)
  // For Android emulator, use 10.0.2.2:8000; for iOS simulator or desktop, use 127.0.0.1:8000
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

/// Root widget for the PEIT Mobile application with Material 3 styling.
class PeitApp extends StatelessWidget {
  final AppDatabase database;
  final SyncService syncService;
  final SecureStorageService secureStorage;
  final PairingService pairingService;

  const PeitApp({
    super.key,
    required this.database,
    required this.syncService,
    required this.secureStorage,
    required this.pairingService,
  });

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
      home: HomeScreen(
        database: database,
        syncService: syncService,
        secureStorage: secureStorage,
        pairingService: pairingService,
      ),
    );
  }
}
