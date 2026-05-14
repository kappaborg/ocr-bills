export type ReceiptItem = {
  id: number;
  item_name: string;
  quantity?: number | null;
  unit_price?: number | null;
  item_price: number;
  category_id?: number | null;
  category_name?: string | null;
  confidence_score?: number;
};

export type ReceiptOut = {
  id: number;
  processing_status: string;
  processing_error?: string | null;
  raw_text?: string | null;
  detected_language?: string | null;
  receipt_date?: string | null;
  store_name?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  items: ReceiptItem[];
};

export type TransactionOut = {
  id: number;
  receipt_id: number;
  date?: string | null;
  store_name?: string | null;
  item_name: string;
  quantity?: number | null;
  unit_price?: number | null;
  item_price: number;
  category_name?: string | null;
};

export type InsightOut = {
  id: number;
  type: string;
  message: string;
  metadata_json?: Record<string, unknown>;
  created_at: string;
};

export type InventoryItemOut = {
  product_id: number;
  product_name: string;
  category_id?: number | null;
  category_name?: string | null;
  last_purchased_at?: string | null;
  purchase_count: number;
  avg_interval_days?: number | null;
  next_expected_buy_date?: string | null;
};

export type NeedToBuyItemOut = {
  product_id: number;
  product_name: string;
  category_name?: string | null;
  last_purchased_at?: string | null;
  next_expected_buy_date?: string | null;
  score: number;
};

