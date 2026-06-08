import 'receipt_item.dart';

class Receipt {
  final int id;
  final String processingStatus;
  final String? processingError;
  final String? rawText;
  final String? detectedLanguage;
  final DateTime? receiptDate;
  final String? storeName;
  final double? totalAmount;
  final double? taxAmount;
  final String? currency;
  final List<ReceiptItem> items;

  const Receipt({
    required this.id,
    required this.processingStatus,
    this.processingError,
    this.rawText,
    this.detectedLanguage,
    this.receiptDate,
    this.storeName,
    this.totalAmount,
    this.taxAmount,
    this.currency,
    required this.items,
  });

  factory Receipt.fromJson(Map<String, dynamic> json) => Receipt(
        id: json['id'] as int,
        processingStatus: json['processing_status'] as String,
        processingError: json['processing_error'] as String?,
        rawText: json['raw_text'] as String?,
        detectedLanguage: json['detected_language'] as String?,
        receiptDate: json['receipt_date'] != null ? DateTime.tryParse(json['receipt_date'] as String) : null,
        storeName: json['store_name'] as String?,
        totalAmount: (json['total_amount'] as num?)?.toDouble(),
        taxAmount: (json['tax_amount'] as num?)?.toDouble(),
        currency: json['currency'] as String?,
        items: (json['items'] as List<dynamic>? ?? []).map((e) => ReceiptItem.fromJson(e as Map<String, dynamic>)).toList(),
      );

  bool get isProcessing => processingStatus == 'queued' || processingStatus == 'processing';
  bool get isParsed => processingStatus == 'parsed';
  bool get isConfirmed => processingStatus == 'confirmed';
  bool get isError => processingStatus == 'error';

  Receipt copyWith({
    String? processingStatus,
    String? processingError,
    String? storeName,
    double? totalAmount,
    double? taxAmount,
    String? currency,
    List<ReceiptItem>? items,
  }) {
    return Receipt(
      id: id,
      processingStatus: processingStatus ?? this.processingStatus,
      processingError: processingError ?? this.processingError,
      rawText: rawText,
      detectedLanguage: detectedLanguage,
      receiptDate: receiptDate,
      storeName: storeName ?? this.storeName,
      totalAmount: totalAmount ?? this.totalAmount,
      taxAmount: taxAmount ?? this.taxAmount,
      currency: currency ?? this.currency,
      items: items ?? this.items,
    );
  }
}
