import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

/// Storage backend interface allowing transparent switching between
/// real Keychain/Keystore (FlutterSecureStorage) and in-memory mock storage (unit tests).
abstract class SecureStorageBackend {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
  Future<void> deleteAll();
}

/// Production implementation backed by FlutterSecureStorage (iOS Keychain / Android EncryptedSharedPreferences).
class FlutterSecureStorageBackend implements SecureStorageBackend {
  final FlutterSecureStorage _storage;

  FlutterSecureStorageBackend([FlutterSecureStorage? storage])
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
              iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
            );

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) => _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);

  @override
  Future<void> deleteAll() => _storage.deleteAll();
}

/// In-memory implementation for headless unit testing and environments without mobile OS Keyring.
class InMemorySecureStorageBackend implements SecureStorageBackend {
  final Map<String, String> _store = {};

  @override
  Future<String?> read(String key) async => _store[key];

  @override
  Future<void> write(String key, String value) async {
    _store[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    _store.remove(key);
  }

  @override
  Future<void> deleteAll() async {
    _store.clear();
  }
}

/// Persistent Secure Storage Service for PEIT LAN Security Handshake credentials.
///
/// Encapsulates storage of:
/// - Bearer auth token (`peit_auth_token`)
/// - Device UUID identifier (`peit_device_id`)
/// - Device user-facing label (`peit_device_name`)
/// - TLS server certificate SHA-256 fingerprint (`peit_server_fingerprint`)
class SecureStorageService {
  static const String keyAuthToken = 'peit_auth_token';
  static const String keyDeviceId = 'peit_device_id';
  static const String keyDeviceName = 'peit_device_name';
  static const String keyServerFingerprint = 'peit_server_fingerprint';
  static const String keyServerHost = 'peit_server_host';
  static const String keyServerPort = 'peit_server_port';

  final SecureStorageBackend _backend;
  final Uuid _uuid;

  SecureStorageService({
    SecureStorageBackend? backend,
    Uuid? uuid,
  })  : _backend = backend ?? FlutterSecureStorageBackend(),
        _uuid = uuid ?? const Uuid();

  /// Retrieve stored bearer authorization token.
  Future<String?> getAuthToken() => _backend.read(keyAuthToken);

  /// Set or update bearer authorization token.
  Future<void> setAuthToken(String token) => _backend.write(keyAuthToken, token);

  /// Retrieve persistent device ID.
  Future<String?> getDeviceId() => _backend.read(keyDeviceId);

  /// Explicitly store device ID.
  Future<void> setDeviceId(String deviceId) => _backend.write(keyDeviceId, deviceId);

  /// Retrieve existing device ID or generate and persist a fresh RFC 4122 v4 UUID.
  Future<String> getOrCreateDeviceId() async {
    var deviceId = await getDeviceId();
    if (deviceId == null || deviceId.isEmpty) {
      deviceId = _uuid.v4();
      await setDeviceId(deviceId);
    }
    return deviceId;
  }

  /// Retrieve user-friendly device name.
  Future<String?> getDeviceName() => _backend.read(keyDeviceName);

  /// Set user-friendly device name.
  Future<void> setDeviceName(String name) => _backend.write(keyDeviceName, name);

  /// Retrieve expected server TLS certificate SHA-256 fingerprint.
  Future<String?> getServerFingerprint() => _backend.read(keyServerFingerprint);

  /// Store expected server TLS certificate SHA-256 fingerprint.
  Future<void> setServerFingerprint(String fingerprint) =>
      _backend.write(keyServerFingerprint, fingerprint);

  /// Delete expected server TLS certificate SHA-256 fingerprint.
  Future<void> clearServerFingerprint() => _backend.delete(keyServerFingerprint);

  /// Check whether device has an active authorization token.
  Future<bool> isPaired() async {
    final token = await getAuthToken();
    return token != null && token.isNotEmpty;
  }

  /// Revoke and clear local pairing credentials (token, server fingerprint).
  /// Preserves stable device ID for consistent re-pairing identity unless [resetDeviceId] is true.
  Future<void> clearPairingData({bool resetDeviceId = false}) async {
    await _backend.delete(keyAuthToken);
    await _backend.delete(keyServerFingerprint);
    await _backend.delete(keyServerHost);
    await _backend.delete(keyServerPort);
    if (resetDeviceId) {
      await _backend.delete(keyDeviceId);
    }
  }

  /// Completely wipe all stored keys.
  Future<void> wipeAll() => _backend.deleteAll();
}
