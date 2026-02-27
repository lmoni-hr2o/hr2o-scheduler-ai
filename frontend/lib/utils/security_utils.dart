import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SecurityUtils {
  static const String _secretKey = "development-secret-key-12345";
  static String activeEnvironment = "lmoni-hr2o/hr2o-scheduler-ai";

  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    activeEnvironment = prefs.getString('active_env') ?? "";
  }

  static Future<void> setActiveEnvironment(String env) async {
    activeEnvironment = env;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('active_env', env);
  }

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
