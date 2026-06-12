import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/brand.dart';
import '../../../shared/widgets/error_view.dart';
import '../data/shopping_list_repository.dart';
import '../models/shopping_item.dart';

/// Shopping list grouped by cheapest store — the screen you'd hold in a
/// store aisle. Composes Market Pulse: each item's best price decides its
/// group, with a per-store subtotal at the top of each section.
class ShoppingListScreen extends ConsumerStatefulWidget {
  const ShoppingListScreen({super.key});

  @override
  ConsumerState<ShoppingListScreen> createState() => _ShoppingListScreenState();
}

class _ShoppingListScreenState extends ConsumerState<ShoppingListScreen> {
  final _draftCtrl = TextEditingController();

  @override
  void dispose() {
    _draftCtrl.dispose();
    super.dispose();
  }

  Future<void> _add() async {
    final name = _draftCtrl.text.trim();
    if (name.isEmpty) return;
    _draftCtrl.clear();
    try {
      await ref.read(shoppingListProvider.notifier).add(name);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'), backgroundColor: Colors.red));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final listAsync = ref.watch(shoppingListProvider);
    final items = listAsync.valueOrNull ?? const <ShoppingItem>[];
    final done = items.where((i) => i.checked).toList();

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const SectionLabel('Plan'),
            Text('Shopping list', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
          ],
        ),
        toolbarHeight: 68,
        actions: [
          IconButton(
            icon: const Icon(Icons.playlist_add),
            tooltip: 'Add due items',
            onPressed: () => ref.read(shoppingListProvider.notifier).addDue(),
          ),
          if (done.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.remove_done),
              tooltip: 'Clear ${done.length} done',
              onPressed: () => ref.read(shoppingListProvider.notifier).clearDone(),
            ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: TextField(
              controller: _draftCtrl,
              onSubmitted: (_) => _add(),
              textInputAction: TextInputAction.done,
              decoration: InputDecoration(
                hintText: 'Add an item — milk, coffee…',
                isDense: true,
                suffixIcon: IconButton(icon: const Icon(Icons.add), onPressed: _add),
              ),
            ),
          ),
          Expanded(
            child: listAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => ErrorView(
                message: e.toString(),
                onRetry: () => ref.read(shoppingListProvider.notifier).load(),
              ),
              data: (items) {
                if (items.isEmpty) {
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(32),
                      child: Text(
                        'Your list is empty.\nAdd items above, or tap ⊕ to pull in everything that\'s due.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.grey),
                      ),
                    ),
                  );
                }
                return RefreshIndicator(
                  onRefresh: () => ref.read(shoppingListProvider.notifier).load(),
                  child: _GroupedList(items: items),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _GroupedList extends ConsumerWidget {
  final List<ShoppingItem> items;
  const _GroupedList({required this.items});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final open = items.where((i) => !i.checked).toList();
    final done = items.where((i) => i.checked).toList();

    // Group open items by cheapest store; null price data → "Anywhere".
    final groups = <String, ({String display, List<ShoppingItem> items})>{};
    for (final it in open) {
      final best = it.bestOption;
      final key = best?.store ?? '__anywhere';
      final display = best?.storeDisplay ?? 'Anywhere';
      groups.putIfAbsent(key, () => (display: display, items: <ShoppingItem>[]));
      groups[key]!.items.add(it);
    }

    String subtotalFor(List<ShoppingItem> groupItems) {
      final byCcy = <String, double>{};
      for (final it in groupItems) {
        final best = it.bestOption;
        if (best != null) {
          byCcy[best.currency] = (byCcy[best.currency] ?? 0) + best.price * it.quantity;
        }
      }
      return byCcy.entries.map((e) => '${e.value.toStringAsFixed(2)} ${e.key}').join(' + ');
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        for (final entry in groups.entries) ...[
          Padding(
            padding: const EdgeInsets.only(bottom: 8, top: 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    entry.key == '__anywhere' ? 'Anywhere' : 'At ${entry.value.display}',
                    style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
                  ),
                ),
                if (subtotalFor(entry.value.items).isNotEmpty)
                  Text('≈ ${subtotalFor(entry.value.items)}',
                      style: AppTheme.moneyStyle.copyWith(fontSize: 12, color: Brand.emerald)),
              ],
            ),
          ),
          for (final it in entry.value.items) _ItemTile(item: it),
          const SizedBox(height: 12),
        ],
        if (done.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.only(bottom: 8, top: 4),
            child: Text('In the basket',
                style: theme.textTheme.titleSmall?.copyWith(color: theme.colorScheme.outline)),
          ),
          for (final it in done) _ItemTile(item: it),
        ],
      ],
    );
  }
}

class _ItemTile extends ConsumerWidget {
  final ShoppingItem item;
  const _ItemTile({required this.item});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final best = item.bestOption;
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        dense: true,
        leading: Checkbox(
          value: item.checked,
          activeColor: Brand.emerald,
          onChanged: (_) => ref.read(shoppingListProvider.notifier).toggle(item),
        ),
        title: Text(
          item.productName + (item.quantity != 1 ? '  ×${item.quantity.toStringAsFixed(item.quantity % 1 == 0 ? 0 : 1)}' : ''),
          style: item.checked
              ? TextStyle(decoration: TextDecoration.lineThrough, color: theme.colorScheme.outline)
              : null,
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (best != null && !item.checked)
              Text('${best.price.toStringAsFixed(2)} ${best.currency}',
                  style: AppTheme.moneyStyle.copyWith(fontSize: 12)),
            IconButton(
              icon: Icon(Icons.close, size: 16, color: theme.colorScheme.outline),
              onPressed: () => ref.read(shoppingListProvider.notifier).remove(item.id),
            ),
          ],
        ),
        onTap: () => ref.read(shoppingListProvider.notifier).toggle(item),
      ),
    );
  }
}
