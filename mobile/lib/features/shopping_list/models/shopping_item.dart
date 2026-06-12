import '../../inventory/models/inventory_item.dart' show PriceOption;

class ShoppingItem {
  final int id;
  final String productName;
  final double quantity;
  final bool checked;
  final String source;
  final List<PriceOption> priceOptions;

  const ShoppingItem({
    required this.id,
    required this.productName,
    required this.quantity,
    required this.checked,
    required this.source,
    this.priceOptions = const [],
  });

  PriceOption? get bestOption => priceOptions.isEmpty ? null : priceOptions.first;

  factory ShoppingItem.fromJson(Map<String, dynamic> json) => ShoppingItem(
        id: json['id'] as int,
        productName: json['product_name'] as String,
        quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
        checked: json['checked'] == true,
        source: (json['source'] ?? 'manual') as String,
        priceOptions: (json['price_options'] as List<dynamic>? ?? const [])
            .map((e) => PriceOption.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  ShoppingItem copyWith({bool? checked, double? quantity}) => ShoppingItem(
        id: id,
        productName: productName,
        quantity: quantity ?? this.quantity,
        checked: checked ?? this.checked,
        source: source,
        priceOptions: priceOptions,
      );
}
