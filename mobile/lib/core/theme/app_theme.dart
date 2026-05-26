import 'package:flutter/material.dart';

const _seed = Color(0xFF0066CC);

class AppTheme {
  static ThemeData get light => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: _seed),
        cardTheme: const CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(12))),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(10))),
          filled: true,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size.fromHeight(48),
            shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(10))),
          ),
        ),
      );

  static ThemeData get dark => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: _seed, brightness: Brightness.dark),
        cardTheme: const CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(12))),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(10))),
          filled: true,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size.fromHeight(48),
            shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(10))),
          ),
        ),
      );

  // Status colours
  static const statusQueued = Color(0xFF9E9E9E);
  static const statusProcessing = Color(0xFFFF9800);
  static const statusParsed = Color(0xFF2196F3);
  static const statusConfirmed = Color(0xFF4CAF50);
  static const statusError = Color(0xFFF44336);

  static Color statusColor(String status) => switch (status) {
        'queued' => statusQueued,
        'processing' => statusProcessing,
        'parsed' => statusParsed,
        'confirmed' => statusConfirmed,
        'error' => statusError,
        _ => statusQueued,
      };

  // Confidence colours
  static Color confidenceColor(double score) {
    if (score >= 0.7) return statusConfirmed;
    if (score >= 0.4) return statusProcessing;
    return statusError;
  }
}
