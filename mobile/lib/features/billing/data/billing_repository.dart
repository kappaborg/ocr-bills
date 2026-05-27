import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/billing_me.dart';

final billingRepositoryProvider = Provider<BillingRepository>((ref) {
  return BillingRepository(ref.read(apiClientProvider));
});

class BillingRepository {
  final ApiClient _api;
  BillingRepository(this._api);

  Future<BillingMe> getMyBilling() async {
    final res = await _api.get(Endpoints.billingMe);
    return BillingMe.fromJson(res.data as Map<String, dynamic>);
  }
}

final billingMeProvider = FutureProvider<BillingMe>((ref) {
  return ref.read(billingRepositoryProvider).getMyBilling();
});
