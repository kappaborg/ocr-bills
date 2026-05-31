import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/storage/secure_storage.dart';
import '../../features/receipts/data/receipts_repository.dart';

/// Auth-protected 200x200 thumbnail for a receipt.
///
/// Flutter's Image.network supports custom headers natively, so we just feed
/// it the Authorization token. The backend serves a center-cropped JPEG from
/// /receipts/{id}/thumbnail and caches it on disk per receipt.
class ReceiptThumbnail extends ConsumerWidget {
  final int receiptId;
  final double size;
  final BorderRadius borderRadius;

  const ReceiptThumbnail({
    super.key,
    required this.receiptId,
    this.size = 48,
    this.borderRadius = const BorderRadius.all(Radius.circular(10)),
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final fallback = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: borderRadius,
      ),
      child: Icon(Icons.receipt_long, color: theme.colorScheme.onPrimaryContainer),
    );

    return FutureBuilder<String?>(
      future: SecureStorage.getToken(),
      builder: (context, snap) {
        if (snap.data == null) return fallback;
        final url = ref.read(receiptsRepositoryProvider).receiptThumbnailUrl(receiptId);
        return ClipRRect(
          borderRadius: borderRadius,
          child: Image.network(
            url,
            headers: {'Authorization': 'Bearer ${snap.data}'},
            width: size,
            height: size,
            fit: BoxFit.cover,
            // Loading: show the icon placeholder rather than a spinner so the
            // list doesn't flash while thumbs stream in.
            loadingBuilder: (_, child, progress) => progress == null ? child : fallback,
            errorBuilder: (_, __, ___) => fallback,
          ),
        );
      },
    );
  }
}
