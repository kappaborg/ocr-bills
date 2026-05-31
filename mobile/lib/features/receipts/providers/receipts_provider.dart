import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/receipts_repository.dart';
import '../models/receipt.dart';
import '../models/receipt_item.dart';

final receiptsListProvider = StateNotifierProvider<ReceiptsListNotifier, AsyncValue<List<Receipt>>>(
  (ref) => ReceiptsListNotifier(ref.read(receiptsRepositoryProvider)),
);

class ReceiptsListNotifier extends StateNotifier<AsyncValue<List<Receipt>>> {
  final ReceiptsRepository _repo;

  ReceiptsListNotifier(this._repo) : super(const AsyncValue.loading()) {
    load();
  }

  Future<void> load() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _repo.listReceipts());
  }

  void removeById(int id) {
    state.whenData((list) {
      state = AsyncValue.data(list.where((r) => r.id != id).toList());
    });
  }

  void updateReceipt(Receipt updated) {
    state.whenData((list) {
      state = AsyncValue.data([
        for (final r in list)
          if (r.id == updated.id) updated else r,
      ]);
    });
  }
}

final receiptDetailProvider =
    FutureProvider.family.autoDispose<Receipt, int>((ref, id) async {
  final repo = ref.read(receiptsRepositoryProvider);
  return repo.getReceipt(id);
});

// Scanner upload flow
final scannerUploadProvider = StateNotifierProvider.autoDispose<ScannerUploadNotifier, AsyncValue<int?>>(
  (ref) => ScannerUploadNotifier(ref.read(receiptsRepositoryProvider)),
);

class ScannerUploadNotifier extends StateNotifier<AsyncValue<int?>> {
  final ReceiptsRepository _repo;

  ScannerUploadNotifier(this._repo) : super(const AsyncValue.data(null));

  Future<void> uploadFrame(File file) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _repo.uploadFromFrame(file));
  }

  void reset() => state = const AsyncValue.data(null);
}

// Confirm items on a receipt
final confirmReceiptProvider = StateNotifierProvider.autoDispose<ConfirmReceiptNotifier, AsyncValue<Receipt?>>(
  (ref) => ConfirmReceiptNotifier(ref.read(receiptsRepositoryProvider)),
);

class ConfirmReceiptNotifier extends StateNotifier<AsyncValue<Receipt?>> {
  final ReceiptsRepository _repo;

  ConfirmReceiptNotifier(this._repo) : super(const AsyncValue.data(null));

  Future<void> confirm(int receiptId, List<ReceiptItem> items) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _repo.confirmReceipt(receiptId, items.map((i) => i.toConfirmJson()).toList()),
    );
  }
}
