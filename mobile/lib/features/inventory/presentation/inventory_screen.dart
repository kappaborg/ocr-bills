import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/date_formatter.dart';
import '../../../shared/widgets/error_view.dart';
import '../../../shared/widgets/loading_skeleton.dart';
import '../models/inventory_item.dart';
import '../providers/inventory_provider.dart';

class _PriceChip extends StatelessWidget {
  final PriceOption option;
  final bool best;
  const _PriceChip({required this.option, required this.best});

  @override
  Widget build(BuildContext context) {
    final accent = best ? Brand.emerald : Theme.of(context).colorScheme.outline;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: best ? Brand.emerald.withValues(alpha: 0.12) : Colors.transparent,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: accent.withValues(alpha: best ? 0.5 : 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(option.storeDisplay,
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: best ? Brand.emerald : null)),
          const SizedBox(width: 6),
          Text('${option.price.toStringAsFixed(2)} ${option.currency}', style: AppTheme.moneyStyle.copyWith(fontSize: 11)),
          const SizedBox(width: 4),
          Text(
            option.stalenessDays == 0 ? 'today' : '${option.stalenessDays}d',
            style: TextStyle(fontSize: 10, color: Theme.of(context).colorScheme.outline),
          ),
        ],
      ),
    );
  }
}

class InventoryScreen extends ConsumerWidget {
  const InventoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final inventoryAsync = ref.watch(inventoryProvider);
    final needToBuyAsync = ref.watch(needToBuyProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Inventory')),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(inventoryProvider);
          ref.invalidate(needToBuyProvider);
        },
        child: inventoryAsync.when(
          loading: () => const ReceiptListSkeleton(),
          error: (e, _) => ErrorView(message: e.toString(), onRetry: () => ref.invalidate(inventoryProvider)),
          data: (items) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Need to buy section
              needToBuyAsync.when(
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
                data: (needList) {
                  if (needList.isEmpty) return const SizedBox.shrink();
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Need to Buy', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold, color: Colors.orange)),
                      const SizedBox(height: 8),
                      ...needList.map((item) => Card(
                            color: Colors.orange.withValues(alpha: 0.1),
                            child: Padding(
                              padding: const EdgeInsets.only(bottom: 4),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  ListTile(
                                    leading: const Icon(Icons.shopping_cart_outlined, color: Colors.orange),
                                    title: Text(item.productName),
                                    subtitle: item.nextExpectedBuyDate != null
                                        ? Text('Expected: ${formatDate(item.nextExpectedBuyDate)}', style: const TextStyle(fontSize: 12))
                                        : null,
                                    trailing: item.categoryName != null ? Chip(label: Text(item.categoryName!, style: const TextStyle(fontSize: 10))) : null,
                                  ),
                                  // Crowdsourced price chips — cheapest first,
                                  // best deal highlighted in brand emerald.
                                  if (item.priceOptions.isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                                      child: Wrap(
                                        spacing: 6,
                                        runSpacing: 6,
                                        children: [
                                          for (var i = 0; i < item.priceOptions.length; i++)
                                            _PriceChip(option: item.priceOptions[i], best: i == 0),
                                        ],
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          )),
                      const Divider(height: 32),
                    ],
                  );
                },
              ),

              // Full inventory
              Text('All Products', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              if (items.isEmpty)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: Text('No products tracked yet.\nConfirm receipts to build your inventory.', textAlign: TextAlign.center, style: TextStyle(color: Colors.grey)),
                  ),
                )
              else
                ...items.map((item) => Card(
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                          child: Text('${item.purchaseCount}', style: TextStyle(color: Theme.of(context).colorScheme.onPrimaryContainer, fontWeight: FontWeight.bold)),
                        ),
                        title: Text(item.productName),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (item.categoryName != null) Text(item.categoryName!, style: const TextStyle(fontSize: 12)),
                            Text('Last: ${formatDate(item.lastPurchasedAt)}', style: const TextStyle(fontSize: 11, color: Colors.grey)),
                          ],
                        ),
                        trailing: item.avgIntervalDays != null
                            ? Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text('${item.avgIntervalDays!.toStringAsFixed(0)}d', style: const TextStyle(fontWeight: FontWeight.bold)),
                                  const Text('interval', style: TextStyle(fontSize: 10, color: Colors.grey)),
                                ],
                              )
                            : null,
                        isThreeLine: item.categoryName != null,
                      ),
                    )),
            ],
          ),
        ),
      ),
    );
  }
}
