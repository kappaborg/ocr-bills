import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/widgets/error_view.dart';
import '../data/billing_repository.dart';
import '../models/plan.dart';

/// Pricing screen. UI-only for now — CTA buttons surface a "Mobile checkout
/// coming soon" snackbar instead of opening Stripe Checkout. When you wire
/// Stripe up later, just replace the onPressed body in [_PlanCard].
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

class _PlanCard extends StatelessWidget {
  final Plan plan;
  final String currency;
  final bool isCurrent;
  const _PlanCard({required this.plan, required this.currency, required this.isCurrent});

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
                // Mobile Stripe Checkout will land later — for now we just
                // surface a "coming soon" so the screen is functional. When
                // wiring it, replace this with a call to /billing/checkout
                // and launch the returned URL in url_launcher / in-app browser.
                onPressed: (isCurrent || plan.isFree)
                    ? null
                    : () => ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Mobile checkout coming soon — visit the web app to upgrade.')),
                        ),
                style: FilledButton.styleFrom(backgroundColor: _isUpgrade ? accent : null),
                child: Text(isCurrent
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
