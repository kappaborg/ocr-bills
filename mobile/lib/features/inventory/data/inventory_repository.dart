import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/inventory_item.dart';

final inventoryRepositoryProvider = Provider<InventoryRepository>((ref) {
  return InventoryRepository(ref.read(apiClientProvider));
});

class InventoryRepository {
  final ApiClient _api;
  InventoryRepository(this._api);

  Future<List<InventoryItem>> getInventory() async {
    final res = await _api.get(Endpoints.inventory);
    final list = res.data['results'] as List<dynamic>;
    return list.map((e) => InventoryItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<NeedToBuyItem>> getNeedToBuy() async {
    final res = await _api.get(Endpoints.needToBuy);
    final list = res.data['results'] as List<dynamic>;
    return list.map((e) => NeedToBuyItem.fromJson(e as Map<String, dynamic>)).toList();
  }
}
