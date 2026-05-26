class InsightItem {
  final int id;
  final String type;
  final String message;
  final Map<String, dynamic> metadataJson;
  final DateTime createdAt;

  const InsightItem({
    required this.id,
    required this.type,
    required this.message,
    required this.metadataJson,
    required this.createdAt,
  });

  factory InsightItem.fromJson(Map<String, dynamic> json) => InsightItem(
        id: json['id'] as int,
        type: json['type'] as String,
        message: json['message'] as String,
        metadataJson: Map<String, dynamic>.from(json['metadata_json'] as Map? ?? {}),
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class Transaction {
  final int id;
  final int receiptId;
  final DateTime? date;
  final String? storeName;
  final String itemName;
  final double? quantity;
  final double? unitPrice;
  final double itemPrice;
  final String? currency;
  final String? categoryName;

  const Transaction({
    required this.id,
    required this.receiptId,
    this.date,
    this.storeName,
    required this.itemName,
    this.quantity,
    this.unitPrice,
    required this.itemPrice,
    this.currency,
    this.categoryName,
  });

  factory Transaction.fromJson(Map<String, dynamic> json) => Transaction(
        id: json['id'] as int,
        receiptId: json['receipt_id'] as int,
        date: json['date'] != null ? DateTime.tryParse(json['date'] as String) : null,
        storeName: json['store_name'] as String?,
        itemName: json['item_name'] as String,
        quantity: (json['quantity'] as num?)?.toDouble(),
        unitPrice: (json['unit_price'] as num?)?.toDouble(),
        itemPrice: (json['item_price'] as num).toDouble(),
        currency: json['currency'] as String?,
        categoryName: json['category_name'] as String?,
      );
}
