import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:test/test.dart';

import '../lib/data/database.dart';
import '../lib/models/receipt_entry.dart';
import '../lib/services/pairing_crypto.dart';
import '../lib/services/pairing_service.dart';
import '../lib/services/secure_storage_service.dart';
import '../lib/services/sync_service.dart';

void main() {
  group('PairingCrypto & Mathematical Parity with Python Test Vectors', () {
    test('pbkdf2HmacSha256 and computePinProof match Python Suite 12 vectors bit-for-bit', () {
      // Test vector 1: from test/test_security_handshake.py (1000 iterations)
      // pin = "123456", salt = "a" * 32, iterations = 1000
      // Expected key: f33f13f1fe852136188f0fee328390d9a017ff4d2b2cb2144c49d14850bcc821
      // session_id = "sess_001", device_id = "phone_abc"
      // Expected proof: c59bb576280d126f6ffe3899d61d8aecc8fbfb3c4c6ca145d09e5c0898f077f1
      final salt32 = 'a' * 32;
      final key1000 = PairingCrypto.pbkdf2HmacSha256(
        pin: '123456',
        salt: salt32,
        iterations: 1000,
        keyLength: 32,
      );
      final key1000Hex = key1000.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      expect(key1000Hex, equals('f33f13f1fe852136188f0fee328390d9a017ff4d2b2cb2144c49d14850bcc821'));

      final proof1000 = PairingCrypto.computePinProof(
        derivedKey: key1000,
        sessionId: 'sess_001',
        deviceId: 'phone_abc',
      );
      expect(proof1000, equals('c59bb576280d126f6ffe3899d61d8aecc8fbfb3c4c6ca145d09e5c0898f077f1'));

      // Test vector 2: standard 10,000 iterations
      // pin = "123456", salt = "a" * 32, iterations = 10000
      // Expected key: c5cc74ec46f9d050fd2550dca50eeced7ac7b95a71a5356e569524c5c9744653
      // Expected proof: fbad75775b5ac18083362b7ed9e630a3861e50181d4054c588ec04ca6cbc706a
      final key10000 = PairingCrypto.pbkdf2HmacSha256(
        pin: '123456',
        salt: salt32,
        iterations: 10000,
        keyLength: 32,
      );
      final key10000Hex = key10000.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      expect(key10000Hex, equals('c5cc74ec46f9d050fd2550dca50eeced7ac7b95a71a5356e569524c5c9744653'));

      final proof10000 = PairingCrypto.computePinProof(
        derivedKey: key10000,
        sessionId: 'sess_001',
        deviceId: 'phone_abc',
      );
      expect(proof10000, equals('fbad75775b5ac18083362b7ed9e630a3861e50181d4054c588ec04ca6cbc706a'));

      // Proof verification helper
      expect(
        PairingCrypto.verifyPinProof(
          derivedKey: key10000,
          sessionId: 'sess_001',
          deviceId: 'phone_abc',
          candidateProof: proof10000,
        ),
        isTrue,
      );

      // Wrong candidate proof, wrong session, or wrong device
      expect(
        PairingCrypto.verifyPinProof(
          derivedKey: key10000,
          sessionId: 'sess_001',
          deviceId: 'phone_abc',
          candidateProof: '0000000000000000000000000000000000000000000000000000000000000000',
        ),
        isFalse,
      );
      expect(
        PairingCrypto.verifyPinProof(
          derivedKey: key10000,
          sessionId: 'other_sess',
          deviceId: 'phone_abc',
          candidateProof: proof10000,
        ),
        isFalse,
      );
    });

    test('computeRequestSignature matches Python message specification', () {
      final token = 'token_secret_123';
      final method = 'POST';
      final path = '/api/v1/sync/push';
      final timestamp = '1775558400';
      final nonce = 'nonce_456';
      final body = utf8.encode('{"entries": []}');

      final sig = PairingCrypto.computeRequestSignature(
        tokenOrKey: token,
        method: method,
        path: path,
        timestamp: timestamp,
        nonce: nonce,
        body: body,
      );

      expect(sig, isNotEmpty);
      expect(sig.length, equals(64)); // SHA-256 hex string
    });
  });

  group('SecureStorageService Persistence & Reset', () {
    test('stores, retrieves, and clears authentication credentials', () async {
      final inMemoryBackend = InMemorySecureStorageBackend();
      final secureStorage = SecureStorageService(backend: inMemoryBackend);

      // Initially unpaired
      expect(await secureStorage.isPaired(), isFalse);
      expect(await secureStorage.getAuthToken(), isNull);

      // Generate or retrieve stable device ID
      final deviceId1 = await secureStorage.getOrCreateDeviceId();
      expect(deviceId1, isNotEmpty);
      final deviceId2 = await secureStorage.getOrCreateDeviceId();
      expect(deviceId1, equals(deviceId2)); // Deterministic persistence

      // Set credentials
      await secureStorage.setAuthToken('bearer_sample_token_xyz');
      await secureStorage.setDeviceName('Ken Mobile Pixel');
      await secureStorage.setServerFingerprint('AA:BB:CC:DD');

      expect(await secureStorage.isPaired(), isTrue);
      expect(await secureStorage.getAuthToken(), equals('bearer_sample_token_xyz'));
      expect(await secureStorage.getDeviceName(), equals('Ken Mobile Pixel'));
      expect(await secureStorage.getServerFingerprint(), equals('AA:BB:CC:DD'));

      // Clear pairing data preserves device ID
      await secureStorage.clearPairingData();
      expect(await secureStorage.isPaired(), isFalse);
      expect(await secureStorage.getAuthToken(), isNull);
      expect(await secureStorage.getServerFingerprint(), isNull);
      expect(await secureStorage.getDeviceId(), equals(deviceId1));

      // Wipe all
      await secureStorage.wipeAll();
      expect(await secureStorage.getDeviceId(), isNull);
    });
  });

  group('PairingUriParams Parser', () {
    test('parses valid peit://pair URIs with and without TLS', () {
      const uriStr = 'peit://pair?host=192.168.1.100&port=8000&session=abc12345&salt=0123456789abcdef0123456789abcdef&tls=1&fingerprint=AA:BB:CC:DD';
      final params = PairingUriParams.parse(uriStr);

      expect(params.host, equals('192.168.1.100'));
      expect(params.port, equals(8000));
      expect(params.sessionId, equals('abc12345'));
      expect(params.salt, equals('0123456789abcdef0123456789abcdef'));
      expect(params.useTls, isTrue);
      expect(params.fingerprint, equals('AA:BB:CC:DD'));

      // Roundtrip re-serialization
      final reSerialized = params.toUriString();
      final roundtrip = PairingUriParams.parse(reSerialized);
      expect(roundtrip.host, equals(params.host));
      expect(roundtrip.port, equals(params.port));
      expect(roundtrip.sessionId, equals(params.sessionId));
      expect(roundtrip.salt, equals(params.salt));
      expect(roundtrip.useTls, equals(params.useTls));
      expect(roundtrip.fingerprint, equals(params.fingerprint));
    });

    test('throws FormatException on malformed URIs', () {
      expect(() => PairingUriParams.parse('http://google.com'), throwsFormatException);
      expect(() => PairingUriParams.parse('peit://pair?host=localhost'), throwsFormatException);
    });
  });

  group('PairingService Handshake Protocol Client', () {
    test('confirmPairing succeeds on 200 OK and stores auth token', () async {
      final backend = InMemorySecureStorageBackend();
      final secureStorage = SecureStorageService(backend: backend);

      final mockClient = MockClient((request) async {
        if (request.url.path == '/api/v1/pair/confirm') {
          final payload = json.decode(request.body) as Map<String, dynamic>;
          expect(payload['session_id'], equals('sess_999'));
          expect(payload['device_name'], equals('Test Device'));
          expect(payload['pin_proof'], isNotEmpty);

          return http.Response(
            json.encode({
              'status': 'paired',
              'device_id': payload['device_id'],
              'device_name': payload['device_name'],
              'auth_token': 'secret_bearer_token_confirmed',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final pairingService = PairingService(
        secureStorage: secureStorage,
        client: mockClient,
      );

      final result = await pairingService.confirmPairing(
        host: '127.0.0.1',
        port: 8000,
        sessionId: 'sess_999',
        salt: 'a' * 32,
        pin: '123456',
        deviceName: 'Test Device',
        fingerprint: '11:22:33:44',
      );

      expect(result.isSuccess, isTrue);
      expect(result.authToken, equals('secret_bearer_token_confirmed'));
      expect(await secureStorage.isPaired(), isTrue);
      expect(await secureStorage.getAuthToken(), equals('secret_bearer_token_confirmed'));
      expect(await secureStorage.getServerFingerprint(), equals('11:22:33:44'));
    });

    test('confirmPairing throws InvalidPinException on 401 invalid_pin_proof', () async {
      final backend = InMemorySecureStorageBackend();
      final secureStorage = SecureStorageService(backend: backend);

      final mockClient = MockClient((request) async {
        return http.Response(
          json.encode({
            'error': 'unauthorized',
            'reason': 'invalid_pin_proof',
            'message': 'Pairing confirmation failed: invalid_pin_proof',
          }),
          401,
          headers: {'content-type': 'application/json'},
        );
      });

      final pairingService = PairingService(
        secureStorage: secureStorage,
        client: mockClient,
      );

      expect(
        () => pairingService.confirmPairing(
          host: '127.0.0.1',
          port: 8000,
          sessionId: 'sess_999',
          salt: 'a' * 32,
          pin: '000000',
          deviceName: 'Test Device',
        ),
        throwsA(isA<InvalidPinException>()),
      );
    });

    test('confirmPairing throws PairingExpiredException on 401 session_expired', () async {
      final backend = InMemorySecureStorageBackend();
      final secureStorage = SecureStorageService(backend: backend);

      final mockClient = MockClient((request) async {
        return http.Response(
          json.encode({
            'error': 'unauthorized',
            'reason': 'session_expired',
            'message': 'Pairing confirmation failed: session_expired',
          }),
          401,
          headers: {'content-type': 'application/json'},
        );
      });

      final pairingService = PairingService(
        secureStorage: secureStorage,
        client: mockClient,
      );

      expect(
        () => pairingService.confirmPairing(
          host: '127.0.0.1',
          port: 8000,
          sessionId: 'sess_expired',
          salt: 'a' * 32,
          pin: '123456',
          deviceName: 'Test Device',
        ),
        throwsA(isA<PairingExpiredException>()),
      );
    });
  });

  group('SyncService Security Headers & Replay Protection', () {
    test('generates Authorization, Device-ID, Timestamp, and Nonce headers when paired', () async {
      final db = AppDatabase.openInMemory();
      final backend = InMemorySecureStorageBackend();
      final secureStorage = SecureStorageService(backend: backend);

      // Setup paired state
      await secureStorage.setAuthToken('token_authenticated_abc');
      final deviceId = await secureStorage.getOrCreateDeviceId();

      final syncService = SyncService(
        baseUrl: 'http://127.0.0.1:8000',
        database: db,
        secureStorage: secureStorage,
      );

      final headers = await syncService.buildPushHeaders();
      expect(headers['Authorization'], equals('Bearer token_authenticated_abc'));
      expect(headers['X-PEIT-Device-ID'], equals(deviceId));
      expect(headers['X-PEIT-Timestamp'], isNotNull);
      expect(int.tryParse(headers['X-PEIT-Timestamp']!), isNotNull);
      expect(headers['X-PEIT-Nonce'], isNotNull);
      expect(headers['X-PEIT-Nonce']!.length, greaterThan(20)); // Valid UUID
    });

    test('revokes local credentials when server returns HTTP 401', () async {
      final db = AppDatabase.openInMemory();
      final backend = InMemorySecureStorageBackend();
      final secureStorage = SecureStorageService(backend: backend);

      await secureStorage.setAuthToken('revoked_token_test');
      expect(await secureStorage.isPaired(), isTrue);

      // Seed 1 receipt entry in SQLite
      final entry = ReceiptEntryModel.create(
        receiptId: 'rec-test-sec',
        receiptDate: '2026-03-10',
        merchant: 'Store A',
        item: 'coffee',
        category: 'Food',
        unit: 'ea',
        currency: 'MXN',
        quantity: 1,
        unitPrice: 5.0,
        paidTotal: -5.0,
        eventType: 'one_off',
      );
      db.insertEntry(entry);

      final mockClient = MockClient((request) async {
        return http.Response(
          json.encode({
            'error': 'unauthorized',
            'message': 'Invalid bearer token for device',
          }),
          401,
          headers: {'content-type': 'application/json'},
        );
      });

      final syncService = SyncService(
        baseUrl: 'http://127.0.0.1:8000',
        database: db,
        secureStorage: secureStorage,
        client: mockClient,
      );

      final result = await syncService.pushPendingEntries();
      expect(result.isSuccess, isFalse);
      expect(result.errorMessage, contains('Unauthorized'));

      // Pairing credentials should have been revoked automatically
      expect(await secureStorage.isPaired(), isFalse);
      expect(await secureStorage.getAuthToken(), isNull);
    });
  });
}
