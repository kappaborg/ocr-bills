import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/dashboard_repository.dart';
import '../models/insights.dart';

final insightsProvider = FutureProvider<List<InsightItem>>((ref) {
  return ref.read(dashboardRepositoryProvider).getInsights();
});

final transactionsProvider = FutureProvider<List<Transaction>>((ref) {
  return ref.read(dashboardRepositoryProvider).getTransactions();
});

final categoriesProvider = FutureProvider<List<String>>((ref) {
  return ref.read(dashboardRepositoryProvider).getCategories();
});

// Spending by category derived from transactions
final spendingByCategoryProvider = FutureProvider<Map<String, double>>((ref) async {
  final txns = await ref.watch(transactionsProvider.future);
  final map = <String, double>{};
  for (final t in txns) {
    final cat = t.categoryName ?? 'Uncategorized';
    map[cat] = (map[cat] ?? 0) + t.itemPrice;
  }
  return map;
});
