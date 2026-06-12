import 'package:flutter/material.dart';

/// ExTaSy brand tokens — ported from the web frontend's globals.css so the
/// app feels like a continuation of the website.
///
///   Background   slate-950 #020617 (dark) / slate-50 #F8FAFC (light)
///   Surface      slate-900 #0F172A / white
///   Primary      cyan-400  #22D3EE (gradient start)
///   Secondary    emerald-400 #34D399 (gradient end)
///   Text         slate-100 #F1F5F9 / slate-900 #0F172A
///   Muted text   slate-400 #94A3B8 / slate-500 #64748B
class Brand {
  static const slate950 = Color(0xFF020617);
  static const slate900 = Color(0xFF0F172A);
  static const slate800 = Color(0xFF1E293B);
  static const slate400 = Color(0xFF94A3B8);
  static const slate100 = Color(0xFFF1F5F9);
  static const slate50 = Color(0xFFF8FAFC);

  static const cyan = Color(0xFF22D3EE);
  static const emerald = Color(0xFF34D399);
  static const amber = Color(0xFFFBBF24);
  static const red = Color(0xFFF87171);

  /// The signature cyan→emerald gradient used on every primary CTA on the
  /// website. Use via [GradientButton] rather than inline.
  static const ctaGradient = LinearGradient(
    colors: [Color(0xFF06B6D4), Color(0xFF10B981)], // cyan-500 → emerald-500
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
  );
}

class AppTheme {
  static ThemeData get dark {
    const scheme = ColorScheme.dark(
      surface: Brand.slate900,
      onSurface: Brand.slate100,
      primary: Brand.cyan,
      onPrimary: Brand.slate950,
      primaryContainer: Color(0xFF164E63), // cyan-900
      onPrimaryContainer: Color(0xFFA5F3FC), // cyan-200
      secondary: Brand.emerald,
      onSecondary: Brand.slate950,
      tertiary: Color(0xFFA78BFA), // violet-400 (business accent)
      error: Brand.red,
      onError: Brand.slate950,
      outline: Color(0xFF334155), // slate-700
      outlineVariant: Color(0xFF1E293B), // slate-800
      surfaceContainerHighest: Brand.slate800,
    );

    return _base(scheme).copyWith(
      scaffoldBackgroundColor: Brand.slate950,
      appBarTheme: const AppBarTheme(
        backgroundColor: Brand.slate950,
        foregroundColor: Brand.slate100,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      // Glass panel: translucent fill + hairline border like the web's
      // .glass-panel (bg white/3%, border white/10).
      cardTheme: CardThemeData(
        elevation: 0,
        color: Colors.white.withValues(alpha: 0.04),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.10)),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Brand.slate900,
        indicatorColor: Brand.cyan.withValues(alpha: 0.18),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected) ? Brand.cyan : Brand.slate400,
          ),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: states.contains(WidgetState.selected) ? Brand.cyan : Brand.slate400,
          ),
        ),
      ),
    );
  }

  static ThemeData get light {
    const scheme = ColorScheme.light(
      surface: Colors.white,
      onSurface: Brand.slate900,
      primary: Color(0xFF0891B2), // cyan-600 — darker for light-bg contrast
      onPrimary: Colors.white,
      primaryContainer: Color(0xFFCFFAFE), // cyan-100
      onPrimaryContainer: Color(0xFF155E75), // cyan-800
      secondary: Color(0xFF059669), // emerald-600
      onSecondary: Colors.white,
      tertiary: Color(0xFF7C3AED), // violet-600
      error: Color(0xFFDC2626),
      onError: Colors.white,
      outline: Color(0xFFCBD5E1), // slate-300
      outlineVariant: Color(0xFFE2E8F0), // slate-200
      surfaceContainerHighest: Color(0xFFF1F5F9),
    );

    return _base(scheme).copyWith(
      scaffoldBackgroundColor: Brand.slate50,
      appBarTheme: const AppBarTheme(
        backgroundColor: Brand.slate50,
        foregroundColor: Brand.slate900,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
      ),
    );
  }

  static ThemeData _base(ColorScheme scheme) => ThemeData(
        useMaterial3: true,
        colorScheme: scheme,
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.outline),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.outlineVariant),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: scheme.primary, width: 1.5),
          ),
          filled: true,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size.fromHeight(48),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        chipTheme: ChipThemeData(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );

  /// Monospace + tabular numerals for money — matches the web's
  /// `font-mono tabular-nums` treatment of every amount.
  static const moneyStyle = TextStyle(
    fontFamily: 'monospace',
    fontFeatures: [FontFeature.tabularFigures()],
    fontWeight: FontWeight.w600,
  );

  // Status colours — tuned to the web palette (parsed = cyan not blue,
  // confirmed = emerald not material-green).
  static const statusQueued = Brand.slate400;
  static const statusProcessing = Brand.amber;
  static const statusParsed = Brand.cyan;
  static const statusConfirmed = Brand.emerald;
  static const statusError = Brand.red;

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
