class InventoryItem {
  final int productId;
  final String productName;
  final int? categoryId;
  final String? categoryName;
  final DateTime? lastPurchasedAt;
  final int purchaseCount;
  final double? avgIntervalDays;
  final DateTime? nextExpectedBuyDate;

  const InventoryItem({
    required this.productId,
    required this.productName,
    this.categoryId,
    this.categoryName,
    this.lastPurchasedAt,
    required this.purchaseCount,
    this.avgIntervalDays,
    this.nextExpectedBuyDate,
  });

  factory InventoryItem.fromJson(Map<String, dynamic> json) => InventoryItem(
        productId: json['product_id'] as int,
        productName: json['product_name'] as String,
        categoryId: json['category_id'] as int?,
        categoryName: json['category_name'] as String?,
        lastPurchasedAt:
            json['last_purchased_at'] != null ? DateTime.tryParse(json['last_purchased_at'] as String) : null,
        purchaseCount: json['purchase_count'] as int? ?? 0,
        avgIntervalDays: (json['avg_interval_days'] as num?)?.toDouble(),
        nextExpectedBuyDate:
            json['next_expected_buy_date'] != null ? DateTime.tryParse(json['next_expected_buy_date'] as String) : null,
      );
}

class PriceOption {
  final String store;
  final String storeDisplay;
  final double price;
  final String currency;
  final int stalenessDays;

  const PriceOption({
    required this.store,
    required this.storeDisplay,
    required this.price,
    required this.currency,
    required this.stalenessDays,
  });

  factory PriceOption.fromJson(Map<String, dynamic> json) => PriceOption(
        store: json['store'] as String,
        storeDisplay: (json['store_display'] ?? json['store']) as String,
        price: (json['price'] as num).toDouble(),
        currency: json['currency'] as String,
        stalenessDays: (json['staleness_days'] ?? 0) as int,
      );
}

class NeedToBuyItem {
  final int productId;
  final String productName;
  final String? categoryName;
  final DateTime? lastPurchasedAt;
  final DateTime? nextExpectedBuyDate;
  final double score;
  final List<PriceOption> priceOptions;

  const NeedToBuyItem({
    required this.productId,
    required this.productName,
    this.categoryName,
    this.lastPurchasedAt,
    this.nextExpectedBuyDate,
    required this.score,
    this.priceOptions = const [],
  });

  factory NeedToBuyItem.fromJson(Map<String, dynamic> json) => NeedToBuyItem(
        productId: json['product_id'] as int,
        productName: json['product_name'] as String,
        categoryName: json['category_name'] as String?,
        lastPurchasedAt:
            json['last_purchased_at'] != null ? DateTime.tryParse(json['last_purchased_at'] as String) : null,
        nextExpectedBuyDate:
            json['next_expected_buy_date'] != null ? DateTime.tryParse(json['next_expected_buy_date'] as String) : null,
        score: (json['score'] as num).toDouble(),
        priceOptions: (json['price_options'] as List<dynamic>? ?? const [])
            .map((e) => PriceOption.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
