import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/storage/secure_storage.dart';
import '../../../shared/widgets/brand.dart';
import '../../receipts/data/receipts_repository.dart';
import '../../receipts/providers/receipts_provider.dart';
import '../providers/onboarded_provider.dart';

/// Three-step first-launch wizard mirroring the web onboarding:
///   1. Welcome + pick display currency
///   2. How to scan a receipt
///   3. Wrap-up + optionally seed sample data
///
/// On completion we set the `onboarded_v1` flag in secure storage so the
/// router stops redirecting here. Skippable from every step.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  static const _currencies = ['BAM', 'EUR', 'USD', 'GBP', 'TRY', 'RUB'];
  final _pageCtrl = PageController();
  int _step = 0;
  String _currency = 'BAM';
  bool _busy = false;

  @override
  void dispose() {
    _pageCtrl.dispose();
    super.dispose();
  }

  void _go(int step) {
    setState(() => _step = step);
    _pageCtrl.animateToPage(step, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
  }

  Future<void> _finish({bool seedSamples = false}) async {
    if (_busy) return;
    setState(() => _busy = true);
    await SecureStorage.saveDisplayCurrency(_currency);
    if (seedSamples) {
      try {
        await ref.read(receiptsRepositoryProvider).seedSampleReceipts();
        ref.read(receiptsListProvider.notifier).load();
      } catch (_) {
        // Seeding is best-effort — don't block onboarding completion on it.
      }
    }
    await ref.read(onboardedProvider.notifier).markDone();
    if (!mounted) return;
    // The router's redirect listens to onboardedProvider so it'll send us
    // to /home/dashboard automatically — but we go explicitly too in case
    // the user landed here via a deep link.
    context.go('/home/dashboard');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        // Stretch forces children to get the Column's finite width along the
        // cross axis. Without this, Column asks each child for its intrinsic
        // width and the Row→FilledButton chain blows up under the wrong
        // device DPI.
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 16),
            _Stepper(step: _step, total: 3),
            Expanded(
              child: PageView(
                controller: _pageCtrl,
                physics: const NeverScrollableScrollPhysics(),
                onPageChanged: (i) => setState(() => _step = i),
                children: [
                  _StepWelcome(
                    currency: _currency,
                    currencies: _currencies,
                    onCurrency: (c) => setState(() => _currency = c),
                  ),
                  const _StepScan(),
                  _StepWrap(currency: _currency),
                ],
              ),
            ),
            // OverflowBar is Material's purpose-built action bar widget. It
            // handles intrinsic sizing of children correctly (FilledButton
            // inside a Row was tripping an infinite-width constraint on
            // some devices — OverflowBar avoids that whole layout pass).
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: OverflowBar(
                alignment: MainAxisAlignment.spaceBetween,
                spacing: 8,
                overflowSpacing: 8,
                children: [
                  TextButton(
                    onPressed: _busy ? null : () => _finish(),
                    child: const Text('Skip'),
                  ),
                  OverflowBar(
                    spacing: 8,
                    overflowSpacing: 8,
                    children: [
                      if (_step > 0)
                        OutlinedButton(
                          onPressed: _busy ? null : () => _go(_step - 1),
                          child: const Text('Back'),
                        ),
                      if (_step < 2)
                        SizedBox(
                          width: 110,
                          child: GradientButton(
                            onPressed: _busy ? null : () => _go(_step + 1),
                            child: const Text('Next'),
                          ),
                        )
                      else ...[
                        OutlinedButton(
                          onPressed: _busy ? null : () => _finish(seedSamples: true),
                          child: const Text('Samples'),
                        ),
                        SizedBox(
                          width: 110,
                          child: GradientButton(
                            onPressed: _busy ? null : () => _finish(),
                            child: _busy
                                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                                : const Text('Start'),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  final int step, total;
  const _Stepper({required this.step, required this.total});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(total, (i) {
          return AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.symmetric(horizontal: 4),
            height: 4,
            width: i == step ? 28 : 16,
            decoration: BoxDecoration(
              color: i <= step ? theme.colorScheme.primary : theme.colorScheme.outlineVariant,
              borderRadius: BorderRadius.circular(2),
            ),
          );
        }),
      ),
    );
  }
}

class _StepWelcome extends StatelessWidget {
  final String currency;
  final List<String> currencies;
  final ValueChanged<String> onCurrency;
  const _StepWelcome({required this.currency, required this.currencies, required this.onCurrency});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.waving_hand_outlined, size: 48, color: theme.colorScheme.primary),
          const SizedBox(height: 16),
          Text('Welcome to ExTaSy', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(
            'Scan receipts, track spending, get smart insights. Let\'s set up your display currency.',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 24),
          Text('Display currency', style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: currencies.map((c) {
              final selected = c == currency;
              return ChoiceChip(
                label: Text(c),
                selected: selected,
                onSelected: (_) => onCurrency(c),
              );
            }).toList(),
          ),
          const SizedBox(height: 12),
          Text(
            'You can change this later in Settings.',
            style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey),
          ),
        ],
      ),
    );
  }
}

class _StepScan extends StatelessWidget {
  const _StepScan();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.qr_code_scanner_outlined, size: 48, color: theme.colorScheme.primary),
          const SizedBox(height: 16),
          Text('Scan or upload a receipt', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          const _Tip(icon: Icons.camera_alt_outlined, text: 'Use the Scan tab to capture a receipt with your camera.'),
          const _Tip(icon: Icons.photo_library_outlined, text: 'Or pick an existing photo from your gallery.'),
          const _Tip(icon: Icons.translate_outlined, text: 'Multi-language: Cyrillic, Arabic, Bosnian, English, and more.'),
          const _Tip(icon: Icons.bolt_outlined, text: 'Live preview shows store + total before the full OCR finishes.'),
        ],
      ),
    );
  }
}

class _StepWrap extends StatelessWidget {
  final String currency;
  const _StepWrap({required this.currency});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.celebration_outlined, size: 48, color: theme.colorScheme.primary),
          const SizedBox(height: 16),
          Text('You\'re all set', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          Text(
            'Default currency: $currency. Want a head start? Tap "Add samples" to load 7 demo '
            'receipts so the dashboard isn\'t empty.',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 24),
          const _Tip(icon: Icons.insights_outlined, text: 'Insights tab surfaces spending spikes and unusual receipts.'),
          const _Tip(icon: Icons.inventory_2_outlined, text: 'Inventory tracks recurring purchases — toilet paper, milk, etc.'),
        ],
      ),
    );
  }
}

class _Tip extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Tip({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
