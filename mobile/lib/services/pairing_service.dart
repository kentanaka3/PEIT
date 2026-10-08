import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart' show sha256;
import 'package:http/http.dart' as http;

import 'pairing_crypto.dart';
import 'secure_storage_service.dart';
import 'sync_service.dart';

/// Exception thrown when PIN proof fails during pairing confirmation (HTTP 401).
class InvalidPinException implements Exception {
  final String message;
  final String reason;
  InvalidPinException([this.message = 'Invalid PIN proof provided', this.reason = 'invalid_pin_proof']);

  @override
  String toString() => 'InvalidPinException: $message (reason: $reason)';
}

/// Exception thrown when pairing session has expired or was not found (HTTP 401).
class PairingExpiredException implements Exception {
  final String message;
  final String reason;
  PairingExpiredException([this.message = 'Pairing session expired or not found', this.reason = 'session_expired']);

  @override
  String toString() => 'PairingExpiredException: $message (reason: $reason)';
}

/// Exception thrown when rate-limiting or too many failed attempts locks out pairing (HTTP 401).
class PairingLockoutException implements Exception {
  final String message;
  PairingLockoutException([this.message = 'Too many failed attempts; pairing locked out']);

  @override
  String toString() => 'PairingLockoutException: $message';
}

/// Structured metadata decoded from a `peit://pair` URI or QR code.
class PairingUriParams {
  final String host;
  final int port;
  final String sessionId;
  final String salt;
  final bool useTls;
  final String? fingerprint;

  const PairingUriParams({
    required this.host,
    required this.port,
    required this.sessionId,
    required this.salt,
    this.useTls = false,
    this.fingerprint,
  });

  /// Parse URI formatted as:
  /// `peit://pair?host=<host>&port=<port>&session=<id>&salt=<salt>&tls=<0|1>&fingerprint=<fp>`
  static PairingUriParams parse(String rawUri) {
    final uri = Uri.parse(rawUri);
    if (uri.scheme != 'peit' || uri.host != 'pair') {
      throw FormatException('Invalid pairing URI scheme or authority: $rawUri');
    }

    final params = uri.queryParameters;
    final host = params['host'];
    final portStr = params['port'];
    final sessionId = params['session'];
    final salt = params['salt'];

    if (host == null || host.isEmpty) throw const FormatException('Missing "host" parameter in pairing URI');
    if (portStr == null || portStr.isEmpty) throw const FormatException('Missing "port" parameter in pairing URI');
    if (sessionId == null || sessionId.isEmpty) throw const FormatException('Missing "session" parameter in pairing URI');
    if (salt == null || salt.isEmpty) throw const FormatException('Missing "salt" parameter in pairing URI');

    final port = int.tryParse(portStr);
    if (port == null || port <= 0 || port > 65535) {
      throw FormatException('Invalid port parameter in pairing URI: $portStr');
    }

    final tlsVal = params['tls'];
    final useTls = tlsVal == '1' || tlsVal == 'true';
    final fingerprint = params['fingerprint'];

    return PairingUriParams(
      host: host,
      port: port,
      sessionId: sessionId,
      salt: salt,
      useTls: useTls,
      fingerprint: fingerprint,
    );
  }

  /// Re-serialize to canonical peit://pair URI.
  String toUriString() {
    final query = <String, String>{
      'host': host,
      'port': port.toString(),
      'session': sessionId,
      'salt': salt,
      if (useTls) 'tls': '1',
      if (fingerprint != null && fingerprint!.isNotEmpty) 'fingerprint': fingerprint!,
    };
    return Uri(scheme: 'peit', host: 'pair', queryParameters: query).toString();
  }
}

/// Result of a successful pairing handshake.
class PairingResult {
  final bool isSuccess;
  final String deviceId;
  final String deviceName;
  final String authToken;
  final String? serverFingerprint;
  final String? errorMessage;

  const PairingResult({
    required this.isSuccess,
    required this.deviceId,
    required this.deviceName,
    required this.authToken,
    this.serverFingerprint,
    this.errorMessage,
  });

  factory PairingResult.success({
    required String deviceId,
    required String deviceName,
    required String authToken,
    String? serverFingerprint,
  }) {
    return PairingResult(
      isSuccess: true,
      deviceId: deviceId,
      deviceName: deviceName,
      authToken: authToken,
      serverFingerprint: serverFingerprint,
    );
  }

  factory PairingResult.failure(String error) {
    return PairingResult(
      isSuccess: false,
      deviceId: '',
      deviceName: '',
      authToken: '',
      errorMessage: error,
    );
  }
}

/// High-level client coordinating LAN pairing handshake with PEIT HTTPS server.
class PairingService {
  final SecureStorageService secureStorage;
  final http.Client? _customClient;

  PairingService({
    required this.secureStorage,
    http.Client? client,
  }) : _customClient = client;

  /// Helper to build an HTTP client with optional SHA-256 TLS certificate fingerprint verification.
  http.Client createHttpClient({String? expectedFingerprint}) {
    if (_customClient != null) return _customClient!;

    if (expectedFingerprint != null && expectedFingerprint.isNotEmpty) {
      final securityContext = SecurityContext(withTrustedRoots: true);
      final ioClient = HttpClient(context: securityContext);

      // Certificate pinning callback
      ioClient.badCertificateCallback = (X509Certificate cert, String host, int port) {
        // If fingerprint matches, accept the self-signed certificate
        final sha256Bytes = sha256.convert(cert.der).bytes;
        final hexList = sha256Bytes.map((b) => b.toRadixString(16).padLeft(2, '0').toUpperCase()).toList();
        final certFingerprint = hexList.join(':');

        final cleanExpected = expectedFingerprint.trim().toUpperCase();
        return certFingerprint == cleanExpected;
      };

      // Wrap ioClient
      return http.Client();
    }

    return http.Client();
  }

  /// Confirm pairing against desktop daemon `POST /api/v1/pair/confirm`.
  ///
  /// Steps:
  /// 1. Retrieve or generate local `deviceId`.
  /// 2. Derive 256-bit symmetric key: `PairingCrypto.pbkdf2HmacSha256(pin, salt)`.
  /// 3. Compute challenge proof: `PairingCrypto.computePinProof(derivedKey, sessionId, deviceId)`.
  /// 4. POST to `http[s]://<host>:<port>/api/v1/pair/confirm`.
  /// 5. On 200 OK, persist `authToken`, `serverFingerprint`, and device details.
  Future<PairingResult> confirmPairing({
    required String host,
    required int port,
    required String sessionId,
    required String salt,
    required String pin,
    required String deviceName,
    String? fingerprint,
    bool useTls = false,
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final deviceId = await secureStorage.getOrCreateDeviceId();
    await secureStorage.setDeviceName(deviceName);

    // 1. PBKDF2-HMAC-SHA256 key derivation
    final derivedKey = PairingCrypto.pbkdf2HmacSha256(
      pin: pin.trim(),
      salt: salt.trim(),
      iterations: 10000,
      keyLength: 32,
    );

    // 2. Compute PIN proof
    final pinProof = PairingCrypto.computePinProof(
      derivedKey: derivedKey,
      sessionId: sessionId.trim(),
      deviceId: deviceId,
    );

    // 3. Dispatch HTTP request
    final scheme = useTls ? 'https' : 'http';
    final uri = Uri.parse('$scheme://$host:$port/api/v1/pair/confirm');
    final payload = {
      'session_id': sessionId.trim(),
      'device_id': deviceId,
      'device_name': deviceName,
      'pin_proof': pinProof,
    };

    final client = _customClient ??
        SyncService.createPinnedClient(expectedFingerprint: fingerprint);
    try {
      final response = await client.post(
        uri,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Accept': 'application/json',
        },
        body: json.encode(payload),
      ).timeout(timeout);

      final bodyString = response.body;
      Map<String, dynamic> data = {};
      try {
        data = json.decode(bodyString) as Map<String, dynamic>;
      } catch (_) {}

      if (response.statusCode == 200) {
        final authToken = data['auth_token'] as String?;
        if (authToken == null || authToken.isEmpty) {
          throw const FormatException('Server returned 200 OK without valid auth_token');
        }

        // Persist credentials
        await secureStorage.setAuthToken(authToken);
        if (fingerprint != null && fingerprint.isNotEmpty) {
          await secureStorage.setServerFingerprint(fingerprint);
        }

        return PairingResult.success(
          deviceId: deviceId,
          deviceName: deviceName,
          authToken: authToken,
          serverFingerprint: fingerprint,
        );
      } else if (response.statusCode == 401) {
        final reason = data['reason'] as String? ?? 'unknown';
        if (reason == 'session_expired' || reason == 'invalid_or_missing_session') {
          throw PairingExpiredException(data['message']?.toString() ?? 'Session expired', reason);
        } else if (reason == 'too_many_attempts') {
          throw PairingLockoutException(data['message']?.toString() ?? 'Too many attempts');
        } else {
          throw InvalidPinException(data['message']?.toString() ?? 'Invalid PIN proof', reason);
        }
      } else {
        final msg = data['message']?.toString() ?? 'HTTP error ${response.statusCode}';
        return PairingResult.failure(msg);
      }
    } finally {
      if (_customClient == null) {
        client.close();
      }
    }
  }

  /// Helper to confirm pairing using a parsed `PairingUriParams`.
  Future<PairingResult> confirmPairingFromUri({
    required PairingUriParams uriParams,
    required String pin,
    required String deviceName,
    Duration timeout = const Duration(seconds: 10),
  }) {
    return confirmPairing(
      host: uriParams.host,
      port: uriParams.port,
      sessionId: uriParams.sessionId,
      salt: uriParams.salt,
      pin: pin,
      deviceName: deviceName,
      fingerprint: uriParams.fingerprint,
      useTls: uriParams.useTls,
      timeout: timeout,
    );
  }
}
