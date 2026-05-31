import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/utils/currency_formatter.dart';
import '../models/receipt.dart';
import '../models/receipt_item.dart';
import '../providers/receipts_provider.dart';

/// Confidence buckets — mirror the web frontend so the UX feels identical.
/// High items collapse to a one-line row (user expands only if they want to
/// edit), medium gets a "Review" pill, low gets an amber border + warning.
enum _Conf { high, medium, low }
_Conf _bucket(double score) {
  if (score >= 0.85) return _Conf.high;
  if (score >= 0.60) return _Conf.medium;
  return _Conf.low;
}

class ReceiptConfirmScreen extends ConsumerStatefulWidget {
  final int receiptId;
  const ReceiptConfirmScreen({super.key, required this.receiptId});

  @override
  ConsumerState<ReceiptConfirmScreen> createState() => _ReceiptConfirmScreenState();
}

class _ReceiptConfirmScreenState extends ConsumerState<ReceiptConfirmScreen> {
  List<ReceiptItem> _items = [];
  // null = follow default (high-conf collapsed); true/false = user override.
  final Map<int, bool?> _expanded = {};
  Receipt? _receipt;
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      _initialized = true;
      _loadReceipt();
    }
  }

  Future<void> _loadReceipt() async {
    final result = await ref.read(receiptDetailProvider(widget.receiptId).future);
    setState(() {
      _receipt = result;
      _items = List.from(result.items);
    });
  }

  void _addItem() {
    setState(() {
      _items.add(const ReceiptItem(id: -1, itemName: '', quantity: 1, itemPrice: 0, confidenceScore: 1));
      _expanded[_items.length - 1] = true;
    });
  }

  void _removeItem(int index) {
    setState(() {
      _items.removeAt(index);
      _expanded.remove(index);
    });
  }

  void _updateItem(int index, ReceiptItem updated) {
    setState(() => _items[index] = updated);
  }

  Future<void> _confirm() async {
    final valid = _items.every((i) => i.itemName.trim().isNotEmpty && i.itemPrice >= 0);
    if (!valid) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Please fill in all item names and valid prices')));
      return;
    }
    await ref.read(confirmReceiptProvider.notifier).confirm(widget.receiptId, _items);
    final state = ref.read(confirmReceiptProvider);
    if (state.hasError && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(state.error.toString()), backgroundColor: Colors.red));
      return;
    }
    if (mounted) {
      ref.invalidate(receiptsListProvider);
      context.pop();
    }
  }

  /// Sum of (qty × price) across all items — used to detect OCR drift vs the
  /// receipt's total_amount. >1% gap triggers the warning banner.
  double get _itemsSum =>
      _items.fold<double>(0, (acc, it) => acc + (it.quantity * it.itemPrice));

  @override
  Widget build(BuildContext context) {
    final confirming = ref.watch(confirmReceiptProvider).isLoading;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Confirm Items'),
        actions: [
          IconButton(icon: const Icon(Icons.add), onPressed: _addItem, tooltip: 'Add item'),
        ],
      ),
      body: _receipt == null
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _SumMismatchBanner(receipt: _receipt!, itemsSum: _itemsSum),
                Expanded(
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (_, i) {
                      final item = _items[i];
                      final bucket = _bucket(item.confidenceScore);
                      final userExpand = _expanded[i];
                      final isExpanded = userExpand ?? (bucket != _Conf.high);
                      return _ItemRow(
                        item: item,
                        bucket: bucket,
                        currency: _receipt!.currency,
                        expanded: isExpanded,
                        onToggle: () => setState(() => _expanded[i] = !isExpanded),
                        onChanged: (u) => _updateItem(i, u),
                        onDelete: () => _removeItem(i),
                      );
                    },
                  ),
                ),
                SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(
                            'Items total: ${formatAmount(_itemsSum, _receipt!.currency)}',
                            style: theme.textTheme.bodySmall,
                            textAlign: TextAlign.center,
                          ),
                        ),
                        FilledButton.icon(
                          onPressed: confirming ? null : _confirm,
                          icon: confirming
                              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Icon(Icons.check),
                          label: const Text('Confirm Receipt'),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

class _SumMismatchBanner extends StatelessWidget {
  final Receipt receipt;
  final double itemsSum;
  const _SumMismatchBanner({required this.receipt, required this.itemsSum});

  @override
  Widget build(BuildContext context) {
    final total = receipt.totalAmount ?? 0;
    if (total <= 0 || itemsSum <= 0) return const SizedBox.shrink();
    final delta = (total - itemsSum).abs();
    final ratio = delta / total;
    if (ratio <= 0.01) return const SizedBox.shrink();

    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      color: Colors.amber.withValues(alpha: 0.15),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Colors.amber, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              "Items don't add up to the receipt total "
              "(${formatAmount(itemsSum, receipt.currency)} vs ${formatAmount(total, receipt.currency)}). "
              "Check the highlighted lines.",
              style: theme.textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

class _ItemRow extends StatefulWidget {
  final ReceiptItem item;
  final _Conf bucket;
  final String? currency;
  final bool expanded;
  final VoidCallback onToggle;
  final ValueChanged<ReceiptItem> onChanged;
  final VoidCallback onDelete;

  const _ItemRow({
    required this.item,
    required this.bucket,
    required this.currency,
    required this.expanded,
    required this.onToggle,
    required this.onChanged,
    required this.onDelete,
  });

  @override
  State<_ItemRow> createState() => _ItemRowState();
}

class _ItemRowState extends State<_ItemRow> {
  late TextEditingController _nameCtrl;
  late TextEditingController _priceCtrl;
  late TextEditingController _qtyCtrl;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.item.itemName);
    _priceCtrl = TextEditingController(text: widget.item.itemPrice.toStringAsFixed(2));
    _qtyCtrl = TextEditingController(text: widget.item.quantity.toStringAsFixed(1));
  }

  @override
  void didUpdateWidget(covariant _ItemRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    // If the underlying item changed externally (e.g. add/remove shifted
    // indexes), resync the controllers so we don't show stale text.
    if (oldWidget.item != widget.item) {
      _nameCtrl.text = widget.item.itemName;
      _priceCtrl.text = widget.item.itemPrice.toStringAsFixed(2);
      _qtyCtrl.text = widget.item.quantity.toStringAsFixed(1);
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _priceCtrl.dispose();
    _qtyCtrl.dispose();
    super.dispose();
  }

  void _notify() {
    widget.onChanged(widget.item.copyWith(
      itemName: _nameCtrl.text,
      itemPrice: double.tryParse(_priceCtrl.text) ?? 0,
      quantity: double.tryParse(_qtyCtrl.text) ?? 1,
    ));
  }

  Color get _borderColor {
    switch (widget.bucket) {
      case _Conf.low:    return Colors.amber.shade400;
      case _Conf.medium: return Colors.blueGrey.shade300;
      case _Conf.high:   return Colors.transparent;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.expanded) return _collapsedView();
    return _expandedView();
  }

  Widget _collapsedView() {
    return InkWell(
      onTap: widget.onToggle,
      borderRadius: BorderRadius.circular(12),
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  widget.item.itemName.isEmpty ? '(unnamed)' : widget.item.itemName,
                  style: const TextStyle(fontWeight: FontWeight.w500),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (widget.item.quantity != 1)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Text('${widget.item.quantity.toStringAsFixed(widget.item.quantity % 1 == 0 ? 0 : 1)}×',
                      style: const TextStyle(color: Colors.grey)),
                ),
              Text(
                formatAmount(widget.item.itemPrice, widget.currency),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right, size: 18, color: Colors.grey),
            ],
          ),
        ),
      ),
    );
  }

  Widget _expandedView() {
    final theme = Theme.of(context);
    return Card(
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: _borderColor, width: widget.bucket == _Conf.low ? 1.5 : 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            if (widget.bucket == _Conf.low)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(children: [
                  Icon(Icons.error_outline, color: Colors.amber.shade700, size: 16),
                  const SizedBox(width: 6),
                  Text(
                    'Looks unclear — double-check the price + name',
                    style: theme.textTheme.bodySmall?.copyWith(color: Colors.amber.shade700),
                  ),
                ]),
              )
            else if (widget.bucket == _Conf.medium)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.blueGrey.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text('Review',
                        style: theme.textTheme.labelSmall?.copyWith(color: Colors.blueGrey.shade200)),
                  ),
                ),
              ),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _nameCtrl,
                    decoration: const InputDecoration(labelText: 'Item name', isDense: true),
                    onChanged: (_) => _notify(),
                  ),
                ),
                IconButton(icon: const Icon(Icons.delete_outline, color: Colors.red), onPressed: widget.onDelete),
                IconButton(
                  icon: Icon(widget.bucket == _Conf.high ? Icons.expand_less : Icons.expand_less_outlined, size: 18),
                  tooltip: 'Collapse',
                  onPressed: widget.bucket == _Conf.high ? widget.onToggle : null,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _qtyCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Qty', isDense: true),
                    onChanged: (_) => _notify(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    controller: _priceCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Price', isDense: true),
                    onChanged: (_) => _notify(),
                  ),
                ),
              ],
            ),
            if (widget.item.categoryName != null)
              Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Chip(
                    label: Text(widget.item.categoryName!, style: const TextStyle(fontSize: 11)),
                    padding: EdgeInsets.zero,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
