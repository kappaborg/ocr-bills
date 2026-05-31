import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/secure_storage.dart';

/// App-wide theme mode persisted in secure storage.
///
/// Mirrors the web frontend: three states (light / dark / system). On launch
/// we hydrate from disk; user toggles via Settings get written back so the
/// preference survives restarts.
class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier() : super(ThemeMode.system) {
    _hydrate();
  }

  Future<void> _hydrate() async {
    final saved = await SecureStorage.getTheme();
    switch (saved) {
      case 'light': state = ThemeMode.light; break;
      case 'dark':  state = ThemeMode.dark;  break;
      case 'system':
      case null:
      default:      state = ThemeMode.system;
    }
  }

  Future<void> set(ThemeMode mode) async {
    state = mode;
    await SecureStorage.saveTheme(mode.name);
  }
}

final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>(
  (ref) => ThemeModeNotifier(),
);
