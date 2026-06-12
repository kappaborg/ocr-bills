import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../models/shopping_item.dart';

final shoppingListRepositoryProvider = Provider<ShoppingListRepository>((ref) {
  return ShoppingListRepository(ref.read(apiClientProvider));
});

class ShoppingListRepository {
  final ApiClient _api;
  ShoppingListRepository(this._api);

  Future<List<ShoppingItem>> getList() async {
    final res = await _api.get('/shopping-list');
    final list = res.data['items'] as List<dynamic>;
    return list.map((e) => ShoppingItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ShoppingItem> addItem(String productName, {double quantity = 1}) async {
    final res = await _api.post('/shopping-list', data: {
      'product_name': productName,
      'quantity': quantity,
    });
    return ShoppingItem.fromJson(res.data as Map<String, dynamic>);
  }

  Future<List<ShoppingItem>> addDueItems() async {
    final res = await _api.post('/shopping-list/from-need-to-buy', data: {});
    final list = res.data['items'] as List<dynamic>;
    return list.map((e) => ShoppingItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> setChecked(int id, bool checked) async {
    await _api.patch('/shopping-list/$id', data: {'checked': checked});
  }

  Future<void> deleteItem(int id) async {
    await _api.delete('/shopping-list/$id');
  }

  Future<void> clearChecked() async {
    await _api.delete('/shopping-list/checked');
  }
}

final shoppingListProvider =
    StateNotifierProvider<ShoppingListNotifier, AsyncValue<List<ShoppingItem>>>(
  (ref) => ShoppingListNotifier(ref.read(shoppingListRepositoryProvider)),
);

class ShoppingListNotifier extends StateNotifier<AsyncValue<List<ShoppingItem>>> {
  final ShoppingListRepository _repo;
  ShoppingListNotifier(this._repo) : super(const AsyncValue.loading()) {
    load();
  }

  Future<void> load() async {
    state = await AsyncValue.guard(() => _repo.getList());
  }

  Future<void> add(String name) async {
    await _repo.addItem(name);
    await load();
  }

  Future<void> addDue() async {
    state = await AsyncValue.guard(() => _repo.addDueItems());
  }

  Future<void> toggle(ShoppingItem item) async {
    // Optimistic flip; reload on failure.
    final current = state.valueOrNull;
    if (current != null) {
      state = AsyncValue.data([
        for (final i in current) i.id == item.id ? i.copyWith(checked: !item.checked) : i,
      ]);
    }
    try {
      await _repo.setChecked(item.id, !item.checked);
    } catch (_) {
      await load();
    }
  }

  Future<void> remove(int id) async {
    final current = state.valueOrNull;
    if (current != null) {
      state = AsyncValue.data([for (final i in current) if (i.id != id) i]);
    }
    try {
      await _repo.deleteItem(id);
    } catch (_) {
      await load();
    }
  }

  Future<void> clearDone() async {
    await _repo.clearChecked();
    await load();
  }
}
