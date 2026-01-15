import 'dart:convert';
import 'package:crypto/crypto.dart';

class SecurityUtils {
  static const String _secretKey = "development-secret-key-12345";
  static String activeEnvironment = "OVERCLEAN"; // Default changed to production-like

  /// Generates an HMAC SHA-256 signature for the given payload.
  static String generateSignature(String payload) {
    final key = utf8.encode(_secretKey);
    final bytes = utf8.encode(payload);

    final hmacSha256 = Hmac(sha256, key);
    final digest = hmacSha256.convert(bytes);

    return digest.toString();
  }

  /// Helper to get standard headers for all Agent API calls.
  static Map<String, String> getHeaders(String payload) {
    return {
      "Content-Type": "application/json",
      "X-HMAC-Signature": generateSignature(payload),
      "Environment": activeEnvironment,
    };
  }
}
