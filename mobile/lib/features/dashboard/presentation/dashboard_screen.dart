import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/widgets/loading_skeleton.dart';
import '../../../shared/widgets/receipt_card.dart';
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
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
          await ref.read(receiptsListProvider.notifier).load();
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
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
                                Text('Total Spending', style: theme.textTheme.labelMedium?.copyWith(color: theme.colorScheme.onPrimaryContainer)),
                                const SizedBox(height: 4),
                                Text(total.toStringAsFixed(2), style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold, color: theme.colorScheme.onPrimaryContainer)),
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
