import 'package:flutter/material.dart';

class AppTheme {
  // Neo-Professional Cybernetic Palette
  static const Color background = Color(0xFF020408); // Deep Abyss Black
  static const Color surface = Color(0xFF0F172A);    // Dark Slate
  
  static const Color primary = Color(0xFF6366F1);    // Electric Indigo
  static const Color accent = Color(0xFF00E676);     // Fluorescent Green (Success/Action)
  static const Color aiGlow = Color(0xFF8B5CF6);     // Violet (Neural)
  
  static const Color textPrimary = Color(0xFFF1F5F9);
  static const Color textSecondary = Color(0xFF94A3B8);
  
  static const Color danger = Color(0xFFEF4444);     // Red (Risk)
  static const Color warning = Color(0xFFF59E0B);    // Orange (Warning)

  static ThemeData darkTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: background,
    primaryColor: primary,
    fontFamily: 'Roboto', // Default, but explicit
    colorScheme: const ColorScheme.dark(
      primary: primary,
      secondary: accent,
      tertiary: aiGlow,
      surface: surface,
      background: background,
      error: danger,
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
        letterSpacing: -0.5,
      ),
      titleLarge: TextStyle(
        color: textPrimary,
        fontWeight: FontWeight.w700,
        fontSize: 18,
      ),
      bodyLarge: TextStyle(color: textPrimary, fontSize: 16),
      bodyMedium: TextStyle(color: textSecondary, fontSize: 14),
      labelSmall: TextStyle(color: textSecondary, fontSize: 10, letterSpacing: 1.0, fontWeight: FontWeight.bold),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: textPrimary,
        fontSize: 20,
        fontWeight: FontWeight.w900,
        letterSpacing: 1.0,
      ),
    ),
  );

  // Modern Sleek Glass Decoration
  static BoxDecoration glassDecoration({
    double blur = 16, 
    double opacity = 0.05,
    BorderRadius? borderRadius,
    Color borderColor = Colors.white10,
  }) {
    return BoxDecoration(
      color: Colors.white.withOpacity(opacity),
      borderRadius: borderRadius ?? BorderRadius.circular(16),
      border: Border.all(
        color: borderColor,
        width: 1.0,
      ),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withOpacity(0.2),
          blurRadius: 20,
          spreadRadius: -5,
        )
      ]
    );
  }
  
  // Cyber Card Decoration
  static BoxDecoration cyberDecoration({
    Color borderColor = primary,
    double opacity = 0.1,
  }) {
    return BoxDecoration(
      color: borderColor.withOpacity(opacity),
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: borderColor.withOpacity(0.5)),
      boxShadow: [
        BoxShadow(
          color: borderColor.withOpacity(0.1),
          blurRadius: 10,
          spreadRadius: 0,
        )
      ]
    );
  }
}
