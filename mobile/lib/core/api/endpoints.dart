class Endpoints {
  // Auth
  static const register = '/auth/register';
  static const login = '/auth/login';
  static const me = '/auth/me';
  static const profile = '/auth/profile';

  // Receipts
  static const receiptsUpload = '/receipts/upload';
  static const receiptsLivePreview = '/receipts/live-preview';
  static const receiptsFromFrame = '/receipts/from-frame';
  static const receipts = '/receipts';
  static String receiptById(int id) => '/receipts/$id';
  static String receiptImage(int id) => '/receipts/$id/image';
  static String receiptConfirm(int id) => '/receipts/$id/confirm';

  // Transactions
  static const transactions = '/transactions';
  static const transactionsExport = '/transactions/export.csv';

  // Analytics
  static const insights = '/insights';
  static const inventory = '/inventory';
  static const needToBuy = '/recommendations/need-to-buy';

  // Metadata
  static const categories = '/meta/categories';
  static const ocrMeta = '/meta/ocr';

  // Billing
  static const billingPlans = '/billing/plans';
  static const billingMe = '/billing/me';
  static const billingCheckout = '/billing/checkout';
  static const billingPortal = '/billing/portal';

  static const health = '/health';
}
