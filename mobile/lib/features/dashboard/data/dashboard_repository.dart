import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/insights.dart';

final dashboardRepositoryProvider = Provider<DashboardRepository>((ref) {
  return DashboardRepository(ref.read(apiClientProvider));
});

class DashboardRepository {
  final ApiClient _api;
  DashboardRepository(this._api);

  Future<List<InsightItem>> getInsights() async {
    final res = await _api.get(Endpoints.insights);
    final list = (res.data['results'] as List<dynamic>);
    return list.map((e) => InsightItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Transaction>> getTransactions({
    String? dateFrom,
    String? dateTo,
    String? category,
    String? store,
  }) async {
    final res = await _api.get(Endpoints.transactions, queryParameters: {
      if (dateFrom != null) 'date_from': dateFrom,
      if (dateTo != null) 'date_to': dateTo,
      if (category != null) 'category': category,
      if (store != null) 'store': store,
    });
    final list = res.data['results'] as List<dynamic>;
    return list.map((e) => Transaction.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<String>> getCategories() async {
    final res = await _api.get(Endpoints.categories);
    final list = res.data as List<dynamic>;
    return list.map((e) => (e['name'] ?? e.toString()) as String).toList();
  }
}
