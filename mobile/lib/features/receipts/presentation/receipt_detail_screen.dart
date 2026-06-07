import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/storage/secure_storage.dart';
import '../../../shared/utils/currency_formatter.dart';
import '../../../shared/utils/date_formatter.dart';
import '../../../shared/widgets/confidence_indicator.dart';
import '../../../shared/widgets/error_view.dart';
import '../../../shared/widgets/status_badge.dart';
import '../data/receipts_repository.dart';
import '../models/receipt.dart';
import '../providers/receipts_provider.dart';

class ReceiptDetailScreen extends ConsumerStatefulWidget {
  final int receiptId;
  const ReceiptDetailScreen({super.key, required this.receiptId});

  @override
  ConsumerState<ReceiptDetailScreen> createState() => _ReceiptDetailScreenState();
}

class _ReceiptDetailScreenState extends ConsumerState<ReceiptDetailScreen> {
  // Polling fallback: only kicks in if SSE fails (proxy strips event-stream,
  // intermediate network drops, etc.). Web frontend has the same pattern.
  Timer? _pollTimer;
  StreamSubscription<ReceiptStatusEvent>? _sseSub;
  CancelToken? _sseCancel;
  Receipt? _receipt;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _sseSub?.cancel();
    _sseCancel?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await ref.read(receiptsRepositoryProvider).getReceipt(widget.receiptId);
      if (!mounted) return;
      setState(() {
        _receipt = r;
        _loading = false;
      });
      if (r.isProcessing) _subscribeStatus();
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = e.toString(); });
    }
  }

  /// Subscribe to live status via SSE; fall back to polling if the stream
  /// errors. Re-fetches the full receipt on terminal so we get items, etc.
  void _subscribeStatus() {
    _sseSub?.cancel();
    _sseCancel?.cancel();
    _pollTimer?.cancel();

    final stream = ref.read(receiptsRepositoryProvider).streamReceiptStatus(widget.receiptId);
    _sseCancel = stream.cancel;
    _sseSub = stream.events.listen(
      (ev) async {
        if (!mounted) return;
        // Patch the local receipt with the event's fields so the UI reflects
        // intermediate transitions even before we refetch.
        setState(() {
          _receipt = _receipt?.copyWith(
            processingStatus: ev.status,
            storeName: ev.storeName ?? _receipt?.storeName,
            totalAmount: ev.totalAmount ?? _receipt?.totalAmount,
            currency: ev.currency ?? _receipt?.currency,
            processingError: ev.processingError,
          );
        });
        if (ev.isTerminal) {
          // Refetch to pick up items and any other fields the SSE summary skips.
          try {
            final fresh = await ref.read(receiptsRepositoryProvider).getReceipt(widget.receiptId);
            if (!mounted) return;
            setState(() => _receipt = fresh);
            ref.read(receiptsListProvider.notifier).updateReceipt(fresh);
          } catch (_) {}
        }
      },
      onError: (_) {
        // SSE failed (proxy / network) — fall back to the old 2s polling loop.
        if (mounted && (_receipt?.isProcessing ?? false)) _startPolling();
      },
    );
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      try {
        final r = await ref.read(receiptsRepositoryProvider).getReceipt(widget.receiptId);
        if (!mounted) return;
        setState(() => _receipt = r);
        if (!r.isProcessing) {
          _pollTimer?.cancel();
          ref.read(receiptsListProvider.notifier).updateReceipt(r);
        }
      } catch (_) {}
    });
  }

  Future<void> _delete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete receipt?'),
        content: const Text('This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(receiptsRepositoryProvider).deleteReceipt(widget.receiptId);
      ref.read(receiptsListProvider.notifier).removeById(widget.receiptId);
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'), backgroundColor: Colors.red));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Receipt'),
        actions: [
          IconButton(icon: const Icon(Icons.delete_outlined), color: Colors.red, onPressed: _delete),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorView(message: _error!, onRetry: _load)
              : _receipt == null
                  ? const SizedBox.shrink()
                  : _buildBody(theme),
    );
  }

  Widget _buildBody(ThemeData theme) {
    final r = _receipt!;
    return RefreshIndicator(
      onRefresh: _load,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Receipt image
            FutureBuilder<String?>(
              future: SecureStorage.getToken(),
              builder: (context, snap) {
                if (snap.data == null) return const SizedBox.shrink();
                final url = ref.read(receiptsRepositoryProvider).receiptImageUrl(r.id);
                return ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.network(
                    url,
                    headers: {'Authorization': 'Bearer ${snap.data}'},
                    height: 200,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => Container(
                      height: 100,
                      color: theme.colorScheme.surfaceContainerHighest,
                      child: const Center(child: Icon(Icons.receipt_long, size: 48)),
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 16),

            // Metadata
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _infoRow('Store', r.storeName ?? '—'),
                    _infoRow('Date', formatDate(r.receiptDate)),
                    _infoRow('Total', formatAmount(r.totalAmount, r.currency)),
                    _infoRow('Language', r.detectedLanguage ?? '—'),
                    Row(
                      children: [
                        const Text('Status:', style: TextStyle(fontWeight: FontWeight.w500)),
                        const SizedBox(width: 8),
                        StatusBadge(r.processingStatus),
                        if (r.isProcessing) ...[
                          const SizedBox(width: 8),
                          const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            if (r.isParsed)
              FilledButton.icon(
                onPressed: () async {
                  // Await the confirm screen so we can refresh our local
                  // state when it pops back — otherwise the button stays
                  // visible and a re-tap would re-confirm + re-bump inventory.
                  final didConfirm = await context.push<bool>('/receipt/${r.id}/confirm');
                  if (didConfirm == true && mounted) _load();
                },
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Review & Confirm Items'),
              ),

            if (r.isConfirmed && r.items.isNotEmpty) ...[
              Text('Items', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Card(
                child: ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: r.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final item = r.items[i];
                    return ListTile(
                      leading: ConfidenceIndicator(item.confidenceScore),
                      title: Text(item.itemName),
                      subtitle: Text('${item.quantity}× ${item.categoryName ?? ""}'),
                      trailing: Text(formatAmount(item.itemPrice, r.currency), style: const TextStyle(fontWeight: FontWeight.bold)),
                    );
                  },
                ),
              ),
            ],

            if (r.isError)
              Card(
                color: theme.colorScheme.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text('Processing error: ${r.processingError ?? "Unknown error"}',
                      style: TextStyle(color: theme.colorScheme.onErrorContainer)),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          children: [
            SizedBox(width: 80, child: Text('$label:', style: const TextStyle(fontWeight: FontWeight.w500))),
            Expanded(child: Text(value, overflow: TextOverflow.ellipsis)),
          ],
        ),
      );
}
