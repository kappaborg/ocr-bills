import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../models/billing_me.dart';
import '../models/plan.dart';

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

  Future<PlansResponse> listPlans() async {
    final res = await _api.get(Endpoints.billingPlans);
    return PlansResponse.fromJson(res.data as Map<String, dynamic>);
  }

  /// Create a Stripe Checkout session for [planId] ("pro" | "business").
  /// Returns the hosted checkout URL to open in a browser. Throws
  /// AppException (503) when Stripe isn't configured on the server.
  Future<String> createCheckout(String planId) async {
    final res = await _api.post(Endpoints.billingCheckout, data: {'plan': planId});
    return res.data['checkout_url'] as String;
  }
}

final billingMeProvider = FutureProvider<BillingMe>((ref) {
  return ref.read(billingRepositoryProvider).getMyBilling();
});

final plansProvider = FutureProvider<PlansResponse>((ref) {
  return ref.read(billingRepositoryProvider).listPlans();
});
