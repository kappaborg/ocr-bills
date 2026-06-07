/// One pricing tier returned by GET /billing/plans.
///
/// receipts_per_month=null means unlimited (Business tier).
class Plan {
  final String id;          // "free" | "pro" | "business"
  final String name;
  final int priceCents;
  final int? receiptsPerMonth;
  final List<String> features;

  const Plan({
    required this.id,
    required this.name,
    required this.priceCents,
    required this.receiptsPerMonth,
    required this.features,
  });

  factory Plan.fromJson(Map<String, dynamic> json) => Plan(
        id: json['id'] as String,
        name: json['name'] as String,
        priceCents: (json['price_cents'] ?? 0) as int,
        receiptsPerMonth: json['receipts_per_month'] as int?,
        features: (json['features'] as List<dynamic>? ?? const []).cast<String>(),
      );

  bool get isFree => id == 'free';
  bool get isUnlimited => receiptsPerMonth == null;
}

class PlansResponse {
  final String currency;
  final int trialDays;
  final bool configured; // Stripe key set on the backend?
  final List<Plan> plans;

  const PlansResponse({
    required this.currency,
    required this.trialDays,
    required this.configured,
    required this.plans,
  });

  factory PlansResponse.fromJson(Map<String, dynamic> json) => PlansResponse(
        currency: (json['currency'] ?? 'USD') as String,
        trialDays: (json['trial_days'] ?? 0) as int,
        configured: json['configured'] == true,
        plans: (json['plans'] as List<dynamic>? ?? const [])
            .map((e) => Plan.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
