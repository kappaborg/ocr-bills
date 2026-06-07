import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/widgets/error_view.dart';
import '../../../shared/widgets/loading_skeleton.dart';
import '../../../shared/widgets/receipt_card.dart';
import '../data/receipts_repository.dart';
import '../models/receipt.dart';
import '../providers/receipts_provider.dart';

class ReceiptsListScreen extends ConsumerStatefulWidget {
  const ReceiptsListScreen({super.key});

  @override
  ConsumerState<ReceiptsListScreen> createState() => _ReceiptsListScreenState();
}

class _ReceiptsListScreenState extends ConsumerState<ReceiptsListScreen> {
  // Debounce input so we don't spam /receipts/search on every keystroke;
  // 300ms feels snappy without firing requests mid-word.
  static const _debounce = Duration(milliseconds: 300);
  final _searchCtrl = TextEditingController();
  Timer? _debounceTimer;
  String _activeQuery = '';
  List<Receipt>? _searchResults;
  bool _searching = false;

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _searchCtrl.dispose();
    super.dispose();
  }

  void _onSearchChanged(String text) {
    _debounceTimer?.cancel();
    final trimmed = text.trim();
    if (trimmed.isEmpty) {
      // Empty input → drop back to full list provider.
      setState(() {
        _activeQuery = '';
        _searchResults = null;
        _searching = false;
      });
      return;
    }
    _debounceTimer = Timer(_debounce, () => _runSearch(trimmed));
  }

  Future<void> _runSearch(String q) async {
    setState(() => _searching = true);
    try {
      final results = await ref.read(receiptsRepositoryProvider).searchReceipts(q);
      if (!mounted) return;
      setState(() {
        _activeQuery = q;
        _searchResults = results;
        _searching = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _searching = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Search failed: $e'), backgroundColor: Colors.red),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final receiptsAsync = ref.watch(receiptsListProvider);
    final isSearching = _activeQuery.isNotEmpty;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Receipts'),
        actions: [
          IconButton(
            icon: const Icon(Icons.download_outlined),
            tooltip: 'Export CSV',
            onPressed: () => context.push('/export'),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(64),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: TextField(
              controller: _searchCtrl,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Search receipts, stores, items…',
                isDense: true,
                prefixIcon: _searching
                    ? const Padding(padding: EdgeInsets.all(12), child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)))
                    : const Icon(Icons.search),
                suffixIcon: _searchCtrl.text.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.close, size: 18),
                        onPressed: () {
                          _searchCtrl.clear();
                          _onSearchChanged('');
                        },
                      ),
                filled: true,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
        ),
      ),
      body: isSearching ? _buildSearchBody() : _buildListBody(receiptsAsync),
    );
  }

  Widget _buildSearchBody() {
    final results = _searchResults ?? const <Receipt>[];
    if (results.isEmpty && !_searching) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.search_off, size: 48, color: Theme.of(context).colorScheme.outlineVariant),
              const SizedBox(height: 12),
              Text('No matches for "$_activeQuery"', textAlign: TextAlign.center),
            ],
          ),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: results.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (_, i) => ReceiptCard(receipt: results[i], onTap: () => context.push('/receipt/${results[i].id}')),
    );
  }

  Widget _buildListBody(AsyncValue<List<Receipt>> receiptsAsync) {
    return receiptsAsync.when(
      loading: () => const ReceiptListSkeleton(),
      error: (e, _) => ErrorView(
        message: e.toString(),
        onRetry: () => ref.read(receiptsListProvider.notifier).load(),
      ),
      data: (receipts) {
        if (receipts.isEmpty) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.receipt_long, size: 72, color: Theme.of(context).colorScheme.outlineVariant),
                const SizedBox(height: 16),
                const Text('No receipts yet'),
                const SizedBox(height: 8),
                const Text('Scan a receipt to get started', style: TextStyle(color: Colors.grey)),
              ],
            ),
          );
        }
        return RefreshIndicator(
          onRefresh: () => ref.read(receiptsListProvider.notifier).load(),
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: receipts.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (context, i) {
              final r = receipts[i];
              return Dismissible(
                key: ValueKey(r.id),
                direction: DismissDirection.endToStart,
                background: Container(
                  alignment: Alignment.centerRight,
                  padding: const EdgeInsets.only(right: 16),
                  decoration: BoxDecoration(color: Colors.red, borderRadius: BorderRadius.circular(12)),
                  child: const Icon(Icons.delete, color: Colors.white),
                ),
                confirmDismiss: (_) async {
                  return await showDialog<bool>(
                    context: context,
                    builder: (_) => AlertDialog(
                      title: const Text('Delete receipt?'),
                      content: const Text('This action cannot be undone.'),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                        TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
                      ],
                    ),
                  );
                },
                onDismissed: (_) async {
                  try {
                    await ref.read(receiptsRepositoryProvider).deleteReceipt(r.id);
                    ref.read(receiptsListProvider.notifier).removeById(r.id);
                  } catch (e) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e'), backgroundColor: Colors.red));
                    }
                    ref.read(receiptsListProvider.notifier).load();
                  }
                },
                child: ReceiptCard(receipt: r, onTap: () => context.push('/receipt/${r.id}')),
              );
            },
          ),
        );
      },
    );
  }
}
