import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/inventory_repository.dart';
import '../models/inventory_item.dart';

final inventoryProvider = FutureProvider<List<InventoryItem>>((ref) {
  return ref.read(inventoryRepositoryProvider).getInventory();
});

final needToBuyProvider = FutureProvider<List<NeedToBuyItem>>((ref) {
  return ref.read(inventoryRepositoryProvider).getNeedToBuy();
});
