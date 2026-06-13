import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/preferences/display_currency_provider.dart';
import '../../../shared/widgets/brand.dart';
import '../../../shared/widgets/loading_skeleton.dart';
import '../../../shared/widgets/receipt_card.dart';
import '../../billing/data/billing_repository.dart';
import '../../receipts/data/receipts_repository.dart';
import '../../receipts/providers/receipts_provider.dart';
import '../providers/dashboard_provider.dart';
import 'widgets/spending_chart.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final insightsAsync = ref.watch(insightsProvider);
    final spendingAsync = ref.watch(spendingByCategoryProvider);
    final receiptsAsync = ref.watch(receiptsListProvider);
    final billingAsync = ref.watch(billingMeProvider);
    final displayCcy = ref.watch(displayCurrencyProvider);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const SectionLabel('Overview'),
            Text('Spending pulse', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
          ],
        ),
        toolbarHeight: 68,
        actions: [
          IconButton(icon: const Icon(Icons.insights_outlined), onPressed: () => context.push('/insights')),
          IconButton(icon: const Icon(Icons.settings_outlined), onPressed: () => context.push('/settings')),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(insightsProvider);
          ref.invalidate(spendingByCategoryProvider);
          ref.invalidate(transactionsProvider);
          ref.invalidate(billingMeProvider);
          await ref.read(receiptsListProvider.notifier).load();
        },
        // Empty-state short-circuit: a fresh account on the brand-new
        // dashboard sees "0.00 KM · 0 receipts" and a wall of empty
        // widgets, which reads as "this app does nothing." The hero CTA
        // gives them an unambiguous next step. Only fires when we KNOW
        // the receipts list is empty — during loading we render the
        // normal layout with skeletons so we don't flash the hero in.
        child: receiptsAsync.maybeWhen(
          data: (rs) => rs.isEmpty ? _EmptyDashboardHero() : null,
          orElse: () => null,
        ) ?? SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Plan + quota chip
              billingAsync.when(
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
                data: (b) {
                  final color = b.plan == 'free'
                      ? theme.colorScheme.surfaceContainerHighest
                      : b.plan == 'pro'
                          ? theme.colorScheme.primary.withValues(alpha:0.15)
                          : theme.colorScheme.tertiary.withValues(alpha:0.15);
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: color,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: theme.colorScheme.onSurface.withValues(alpha:0.08),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              b.plan.toUpperCase(),
                              style: theme.textTheme.labelSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              b.isUnlimited
                                  ? 'Unlimited receipts'
                                  : '${b.usage.receiptsUsed} / ${b.usage.receiptsQuota} receipts this month',
                              style: theme.textTheme.bodySmall,
                            ),
                          ),
                          if (b.plan == 'free')
                            TextButton(
                              onPressed: () => context.push('/settings'),
                              style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
                              child: const Text('Upgrade'),
                            ),
                        ],
                      ),
                    ),
                  );
                },
              ),
              // Summary card
              receiptsAsync.when(
                loading: () => const LoadingSkeleton(height: 100),
                error: (_, __) => const SizedBox.shrink(),
                data: (receipts) {
                  final confirmed = receipts.where((r) => r.isConfirmed).toList();
                  final total = confirmed.fold<double>(0, (s, r) => s + (r.totalAmount ?? 0));
                  return Card(
                    color: theme.colorScheme.primaryContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('TOTAL SPENDING',
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: theme.colorScheme.onPrimaryContainer.withValues(alpha: 0.8),
                                      letterSpacing: 1.5,
                                    )),
                                const SizedBox(height: 4),
                                MoneyText(
                                  '${total.toStringAsFixed(2)} $displayCcy',
                                  fontSize: 28,
                                  color: theme.colorScheme.onPrimaryContainer,
                                ),
                              ],
                            ),
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text('${receipts.length}', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold, color: theme.colorScheme.onPrimaryContainer)),
                              Text('receipts', style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onPrimaryContainer)),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 16),

              // Insights banner
              insightsAsync.when(
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
                data: (insights) {
                  if (insights.isEmpty) return const SizedBox.shrink();
                  final first = insights.first;
                  return Card(
                    color: theme.colorScheme.secondaryContainer,
                    child: ListTile(
                      leading: Icon(
                        first.type == 'spending_spike' ? Icons.trending_up : Icons.info_outline,
                        color: theme.colorScheme.onSecondaryContainer,
                      ),
                      title: Text(first.message, style: TextStyle(color: theme.colorScheme.onSecondaryContainer, fontSize: 13)),
                      trailing: TextButton(onPressed: () => context.push('/insights'), child: const Text('View All')),
                    ),
                  );
                },
              ),
              const SizedBox(height: 16),

              // Spending chart
              Text('Spending by Category', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              spendingAsync.when(
                loading: () => const LoadingSkeleton(height: 160),
                error: (_, __) => const SizedBox.shrink(),
                data: (map) => SpendingChart(data: map),
              ),
              const SizedBox(height: 20),

              // Recent receipts
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Recent Receipts', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                  TextButton(onPressed: () => context.go('/home/receipts'), child: const Text('See All')),
                ],
              ),
              const SizedBox(height: 8),
              receiptsAsync.when(
                loading: () => const ReceiptListSkeleton(),
                error: (_, __) => const SizedBox.shrink(),
                data: (receipts) {
                  final recent = receipts.take(5).toList();
                  if (recent.isEmpty) return const Text('No receipts yet.', style: TextStyle(color: Colors.grey));
                  return Column(
                    children: recent.map((r) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: ReceiptCard(receipt: r, onTap: () => context.push('/receipt/${r.id}')),
                    )).toList(),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Shown when the user's confirmed-receipts list is empty. One unambiguous
/// next step (scan now), a quieter secondary path (load samples to explore).
class _EmptyDashboardHero extends ConsumerStatefulWidget {
  @override
  ConsumerState<_EmptyDashboardHero> createState() => _EmptyDashboardHeroState();
}

class _EmptyDashboardHeroState extends ConsumerState<_EmptyDashboardHero> {
  bool _seeding = false;

  Future<void> _addSamples() async {
    setState(() => _seeding = true);
    try {
      await ref.read(receiptsRepositoryProvider).seedSampleReceipts();
      await ref.read(receiptsListProvider.notifier).load();
      ref.invalidate(insightsProvider);
      ref.invalidate(spendingByCategoryProvider);
      ref.invalidate(billingMeProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _seeding = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 12),
          const SectionLabel('Welcome'),
          const SizedBox(height: 6),
          Text(
            'Let\'s see your\nspending pulse',
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w700,
              height: 1.1,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            'Scan a receipt — anything from your wallet works. ExTaSy reads it, '
            'sorts the items, and starts building your dashboard.',
            style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.outline, height: 1.45),
          ),
          const SizedBox(height: 36),

          // Primary CTA — gradient, brand-aligned, unambiguous.
          GradientButton(
            onPressed: () => context.go('/home/scan'),
            icon: const Icon(Icons.camera_alt_outlined, size: 18),
            child: const Text('Scan your first receipt'),
          ),
          const SizedBox(height: 12),

          // Secondary path: load the sample-receipt set so they can
          // poke around the app with realistic data. Quieter visually.
          OutlinedButton.icon(
            onPressed: _seeding ? null : _addSamples,
            icon: _seeding
                ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.auto_awesome_outlined, size: 18),
            label: const Text('Or explore with 7 sample receipts'),
          ),

          const SizedBox(height: 40),

          // What the user gets — three short value bullets. Same icons as
          // onboarding so the message rhymes across screens.
          const _Bullet(icon: Icons.translate_outlined, text: 'Bosnian, English, Arabic, anything — the OCR handles it'),
          const _Bullet(icon: Icons.bolt_outlined, text: 'Live preview before the full scan finishes'),
          const _Bullet(icon: Icons.attach_money_outlined, text: 'Once you have a few, see the cheapest store per item'),
        ],
      ),
    );
  }
}

class _Bullet extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Bullet({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: theme.colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text, style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.outline)),
          ),
        ],
      ),
    );
  }
}
