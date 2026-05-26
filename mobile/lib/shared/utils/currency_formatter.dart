String formatAmount(double? amount, String? currency) {
  if (amount == null) return '—';
  final sym = currency ?? '';
  return '${amount.toStringAsFixed(2)} $sym'.trim();
}
