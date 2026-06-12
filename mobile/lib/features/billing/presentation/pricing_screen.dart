import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../shared/widgets/error_view.dart';
import '../data/billing_repository.dart';
import '../models/plan.dart';

/// Pricing screen. Upgrade buttons create a Stripe Checkout session and
/// open the hosted page in the browser; the webhook flips the plan when
/// payment completes. When Stripe isn't configured server-side
/// (plans.configured == false) the buttons explain instead of failing.
class PricingScreen extends ConsumerWidget {
  const PricingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final plansAsync = ref.watch(plansProvider);
    final myBillingAsync = ref.watch(billingMeProvider);
    final currentPlan = myBillingAsync.valueOrNull?.plan ?? 'free';

    return Scaffold(
      appBar: AppBar(title: const Text('Plans & Pricing')),
      body: plansAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorView(message: e.toString(), onRetry: () => ref.invalidate(plansProvider)),
        data: (resp) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(plansProvider),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              if (resp.trialDays > 0)
                _TrialBanner(days: resp.trialDays),
              const SizedBox(height: 8),
              for (final plan in resp.plans)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _PlanCard(
                    plan: plan,
                    currency: resp.currency,
                    isCurrent: plan.id == currentPlan,
                    configured: resp.configured,
                  ),
                ),
              const SizedBox(height: 12),
              if (!resp.configured)
                Text(
                  'Billing isn\'t fully configured on this server — pricing is shown for reference only.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey),
                  textAlign: TextAlign.center,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TrialBanner extends StatelessWidget {
  final int days;
  const _TrialBanner({required this.days});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.amber.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.workspace_premium_outlined, color: Colors.amber),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'All paid plans start with a $days-day free trial.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}

class _PlanCard extends ConsumerStatefulWidget {
  final Plan plan;
  final String currency;
  final bool isCurrent;
  final bool configured;
  const _PlanCard({required this.plan, required this.currency, required this.isCurrent, required this.configured});

  @override
  ConsumerState<_PlanCard> createState() => _PlanCardState();
}

class _PlanCardState extends ConsumerState<_PlanCard> {
  bool _busy = false;

  Plan get plan => widget.plan;
  String get currency => widget.currency;
  bool get isCurrent => widget.isCurrent;

  Future<void> _checkout() async {
    if (!widget.configured) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Billing is in setup mode — upgrades open soon.')),
      );
      return;
    }
    setState(() => _busy = true);
    try {
      final url = await ref.read(billingRepositoryProvider).createCheckout(plan.id);
      final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
      if (!ok && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open checkout — try again.'), backgroundColor: Colors.red),
        );
      }
      // The Stripe webhook flips the plan when payment completes; refresh
      // billing state when the user comes back to the app.
      ref.invalidate(billingMeProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String get _priceLabel {
    if (plan.priceCents == 0) return 'Free';
    final dollars = plan.priceCents / 100.0;
    final symbol = currency == 'USD' ? '\$' : '$currency ';
    return '$symbol${dollars.toStringAsFixed(dollars.truncateToDouble() == dollars ? 0 : 2)}/mo';
  }

  String get _receiptsLabel {
    if (plan.isUnlimited) return 'Unlimited receipts';
    return '${plan.receiptsPerMonth} receipts / month';
  }

  bool get _isUpgrade => !isCurrent && !plan.isFree;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final accent = plan.id == 'pro'
        ? Colors.cyan
        : plan.id == 'business'
            ? Colors.purple
            : theme.colorScheme.outline;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isCurrent ? accent : Colors.transparent,
          width: isCurrent ? 2 : 0,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(plan.name, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(width: 8),
                if (isCurrent)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text('Current', style: theme.textTheme.labelSmall?.copyWith(color: accent)),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(_priceLabel, style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(_receiptsLabel, style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey)),
            const SizedBox(height: 12),
            for (final f in plan.features)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.check, size: 16, color: accent),
                    const SizedBox(width: 8),
                    Expanded(child: Text(f, style: theme.textTheme.bodySmall)),
                  ],
                ),
              ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: (isCurrent || plan.isFree || _busy) ? null : _checkout,
                style: FilledButton.styleFrom(backgroundColor: _isUpgrade ? accent : null),
                child: _busy
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(isCurrent
                        ? 'You\'re on this plan'
                        : plan.isFree
                            ? 'Default plan'
                            : 'Upgrade to ${plan.name}'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
