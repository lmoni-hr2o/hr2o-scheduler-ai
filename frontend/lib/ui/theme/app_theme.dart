import 'package:flutter/material.dart';

class AppTheme {
  // Ultra-modern color palette (Vibrant & Premium)
  static const Color background = Color(0xFF030712); // Real Black-Blue
  static const Color surface = Color(0xFF111827);    // Deep Gray
  static const Color primary = Color(0xFF8B5CF6);    // Vibrant Violet
  static const Color accent = Color(0xFF06B6D4);     // Cyan
  static const Color aiGlow = Color(0xFFD946EF);     // Fuchsia (for AI elements)
  static const Color textPrimary = Color(0xFFF9FAFB);
  static const Color textSecondary = Color(0xFF9CA3AF);

  static ThemeData darkTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: background,
    primaryColor: primary,
    colorScheme: const ColorScheme.dark(
      primary: primary,
      secondary: accent,
      tertiary: aiGlow,
      surface: surface,
      background: background,
    ),
    textTheme: const TextTheme(
      displaySmall: TextStyle(
        color: textPrimary,
        fontWeight: FontWeight.w900,
        letterSpacing: -1.0,
      ),
      headlineMedium: TextStyle(
        color: textPrimary,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.8,
      ),
      titleLarge: TextStyle(
        color: textPrimary,
        fontWeight: FontWeight.w700,
      ),
      bodyLarge: TextStyle(color: textPrimary, fontSize: 16),
      bodyMedium: TextStyle(color: textSecondary, fontSize: 14),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: textPrimary,
        fontSize: 22,
        fontWeight: FontWeight.w900,
        letterSpacing: -0.5,
      ),
    ),
  );

  // Advanced Glassmorphic decoration helper
  static BoxDecoration glassDecoration({
    double blur = 12, 
    double opacity = 0.08,
    BorderRadius? borderRadius,
  }) {
    return BoxDecoration(
      color: Colors.white.withOpacity(opacity),
      borderRadius: borderRadius ?? BorderRadius.circular(20),
      border: Border.all(
        color: Colors.white.withOpacity(0.12),
        width: 1.0,
      ),
    );
  }
}
