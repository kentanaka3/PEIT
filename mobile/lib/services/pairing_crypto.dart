import 'dart:convert';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';

/// Pure Dart Cryptographic Engine for the PEIT LAN Security Handshake.
///
/// Implements bit-for-bit parity with Python's hashlib PBKDF2-HMAC-SHA256
/// and HMAC-SHA256 challenge-response proofs.
class PairingCrypto {
  /// Pure Dart PBKDF2-HMAC-SHA256 matching Python's:
  /// `hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), iterations, 32)`
  ///
  /// Conforms to RFC 2898 / PKCS #5 v2.0 using HMAC-SHA256 as pseudorandom function (PRF).
  static Uint8List pbkdf2HmacSha256({
    required String pin,
    required String salt,
    int iterations = 10000,
    int keyLength = 32,
  }) {
    final passwordBytes = utf8.encode(pin);
    final saltBytes = utf8.encode(salt);
    return pbkdf2Raw(
      password: Uint8List.fromList(passwordBytes),
      salt: Uint8List.fromList(saltBytes),
      iterations: iterations,
      keyLength: keyLength,
    );
  }

  /// Low-level PBKDF2-HMAC-SHA256 operating on raw byte arrays.
  static Uint8List pbkdf2Raw({
    required Uint8List password,
    required Uint8List salt,
    required int iterations,
    required int keyLength,
  }) {
    const hLen = 32; // SHA-256 digest length in bytes
    final l = (keyLength / hLen).ceil();
    final r = keyLength - (l - 1) * hLen;

    final derivedKey = Uint8List(keyLength);
    var derivedOffset = 0;

    for (var i = 1; i <= l; i++) {
      // U_1 = PRF(P, S || INT_32_BE(i))
      final saltPlusIndex = Uint8List(salt.length + 4);
      saltPlusIndex.setRange(0, salt.length, salt);
      saltPlusIndex[salt.length] = (i >> 24) & 0xff;
      saltPlusIndex[salt.length + 1] = (i >> 16) & 0xff;
      saltPlusIndex[salt.length + 2] = (i >> 8) & 0xff;
      saltPlusIndex[salt.length + 3] = i & 0xff;

      var hmacInstance = Hmac(sha256, password);
      var u = Uint8List.fromList(hmacInstance.convert(saltPlusIndex).bytes);
      final t = Uint8List.fromList(u);

      // U_2 ... U_c
      for (var c = 1; c < iterations; c++) {
        u = Uint8List.fromList(hmacInstance.convert(u).bytes);
        for (var k = 0; k < hLen; k++) {
          t[k] ^= u[k];
        }
      }

      final blockLen = (i == l) ? r : hLen;
      derivedKey.setRange(derivedOffset, derivedOffset + blockLen, t.sublist(0, blockLen));
      derivedOffset += blockLen;
    }

    return derivedKey;
  }

  /// Calculate HMAC-SHA256 proof over session_id + device_id using derived key.
  ///
  /// Matches Python's `compute_pin_proof(derived_key, session_id, device_id)`:
  /// `hmac.new(derived_key, f"{session_id}{device_id}".encode("utf-8"), hashlib.sha256).hexdigest()`
  static String computePinProof({
    required Uint8List derivedKey,
    required String sessionId,
    required String deviceId,
  }) {
    final message = utf8.encode('$sessionId$deviceId');
    final hmacInstance = Hmac(sha256, derivedKey);
    final digest = hmacInstance.convert(message);
    return digest.toString(); // Hex lowercase representation
  }

  /// Verify PIN proof using constant-time comparison.
  static bool verifyPinProof({
    required Uint8List derivedKey,
    required String sessionId,
    required String deviceId,
    required String candidateProof,
  }) {
    final expectedProof = computePinProof(
      derivedKey: derivedKey,
      sessionId: sessionId,
      deviceId: deviceId,
    );
    return constantTimeEquals(expectedProof, candidateProof);
  }

  /// Compute HMAC-SHA256 request signature over HTTP request metadata and body.
  ///
  /// Matches Python's:
  /// `METHOD\nPATH\nTIMESTAMP\nNONCE\nBODY_SHA256`
  static String computeRequestSignature({
    required String tokenOrKey,
    required String method,
    required String path,
    required String timestamp,
    required String nonce,
    List<int> body = const [],
  }) {
    final keyBytes = utf8.encode(tokenOrKey);
    final bodySha256 = sha256.convert(body).toString();
    final messageString = '${method.toUpperCase()}\n$path\n$timestamp\n$nonce\n$bodySha256';
    final messageBytes = utf8.encode(messageString);

    final hmacInstance = Hmac(sha256, keyBytes);
    return hmacInstance.convert(messageBytes).toString();
  }

  /// Constant-time string equality check to prevent timing attacks.
  static bool constantTimeEquals(String a, String b) {
    if (a.length != b.length) return false;
    var result = 0;
    for (var i = 0; i < a.length; i++) {
      result |= a.codeUnitAt(i) ^ b.codeUnitAt(i);
    }
    return result == 0;
  }
}
