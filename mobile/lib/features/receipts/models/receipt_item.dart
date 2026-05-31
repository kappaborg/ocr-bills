class ReceiptItem {
  final int id;
  final String itemName;
  final double quantity;
  final double? unitPrice;
  final double itemPrice;
  final int? categoryId;
  final String? categoryName;
  final double confidenceScore;

  const ReceiptItem({
    required this.id,
    required this.itemName,
    required this.quantity,
    this.unitPrice,
    required this.itemPrice,
    this.categoryId,
    this.categoryName,
    required this.confidenceScore,
  });

  factory ReceiptItem.fromJson(Map<String, dynamic> json) => ReceiptItem(
        id: json['id'] as int,
        itemName: json['item_name'] as String,
        quantity: (json['quantity'] as num?)?.toDouble() ?? 1.0,
        unitPrice: (json['unit_price'] as num?)?.toDouble(),
        itemPrice: (json['item_price'] as num).toDouble(),
        categoryId: json['category_id'] as int?,
        categoryName: json['category_name'] as String?,
        confidenceScore: (json['confidence_score'] as num?)?.toDouble() ?? 0.0,
      );

  ReceiptItem copyWith({
    String? itemName,
    double? quantity,
    double? unitPrice,
    double? itemPrice,
    String? categoryName,
  }) =>
      ReceiptItem(
        id: id,
        itemName: itemName ?? this.itemName,
        quantity: quantity ?? this.quantity,
        unitPrice: unitPrice ?? this.unitPrice,
        itemPrice: itemPrice ?? this.itemPrice,
        categoryId: categoryId,
        categoryName: categoryName ?? this.categoryName,
        confidenceScore: confidenceScore,
      );

  Map<String, dynamic> toConfirmJson() => {
        'id': id > 0 ? id : null,
        'item_name': itemName,
        'quantity': quantity,
        'unit_price': unitPrice,
        'item_price': itemPrice,
        'category_id': categoryId,
      };
}
