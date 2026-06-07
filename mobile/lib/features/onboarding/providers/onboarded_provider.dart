import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/storage/secure_storage.dart';

/// Tri-state onboarded flag:
///   null  → still hydrating from secure storage (block redirect)
///   false → user has not seen the wizard yet
///   true  → wizard completed
class OnboardedNotifier extends StateNotifier<bool?> {
  OnboardedNotifier() : super(null) {
    _hydrate();
  }

  Future<void> _hydrate() async {
    state = await SecureStorage.getOnboarded();
  }

  Future<void> markDone() async {
    await SecureStorage.setOnboarded();
    state = true;
  }
}

final onboardedProvider = StateNotifierProvider<OnboardedNotifier, bool?>(
  (ref) => OnboardedNotifier(),
);
