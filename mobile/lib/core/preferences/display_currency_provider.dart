import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/secure_storage.dart';

/// User's preferred display currency, persisted by the onboarding wizard
/// (or Settings later) in SecureStorage. Falls back to 'BAM' until the
/// async read resolves so the UI doesn't flash an empty unit.
///
/// This is a *display* preference only — receipt totals stay in their
/// captured currency; this code is what labels aggregate sums (dashboard
/// "Total Spending", insights baseline) where the unit is otherwise
/// ambiguous.
class DisplayCurrencyNotifier extends StateNotifier<String> {
  DisplayCurrencyNotifier() : super('BAM') {
    _hydrate();
  }

  Future<void> _hydrate() async {
    final saved = await SecureStorage.getDisplayCurrency();
    if (saved != null && saved.isNotEmpty) state = saved;
  }

  Future<void> set(String code) async {
    state = code;
    await SecureStorage.saveDisplayCurrency(code);
  }
}

final displayCurrencyProvider = StateNotifierProvider<DisplayCurrencyNotifier, String>(
  (ref) => DisplayCurrencyNotifier(),
);
