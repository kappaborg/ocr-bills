class BillingUsage {
  final int receiptsUsed;
  final int receiptsQuota;
  final double percent;

  const BillingUsage({
    required this.receiptsUsed,
    required this.receiptsQuota,
    required this.percent,
  });

  factory BillingUsage.fromJson(Map<String, dynamic> json) => BillingUsage(
        receiptsUsed: (json['receipts_used'] ?? 0) as int,
        receiptsQuota: (json['receipts_quota'] ?? 0) as int,
        percent: ((json['percent'] ?? 0) as num).toDouble(),
      );
}

class BillingMe {
  final String plan;       // 'free' | 'pro' | 'business'
  final String status;
  final DateTime? currentPeriodEnd;
  final BillingUsage usage;

  const BillingMe({
    required this.plan,
    required this.status,
    required this.currentPeriodEnd,
    required this.usage,
  });

  factory BillingMe.fromJson(Map<String, dynamic> json) => BillingMe(
        plan: (json['plan'] ?? 'free') as String,
        status: (json['status'] ?? 'active') as String,
        currentPeriodEnd: json['current_period_end'] != null
            ? DateTime.tryParse(json['current_period_end'] as String)
            : null,
        usage: BillingUsage.fromJson(
          json['usage'] as Map<String, dynamic>,
        ),
      );

  bool get isUnlimited => usage.receiptsQuota == 0;
  bool get isNearCap => !isUnlimited && usage.percent >= 80;
}
