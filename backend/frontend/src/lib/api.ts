import { ReceiptOut, InsightOut, TransactionOut, InventoryItemOut, NeedToBuyItemOut } from "./types";
import { clearAccessToken } from "./auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ApiError = { detail?: string };

function getErrorMessage(payload: unknown): string {
  if (!payload) return "Request failed";
  if (typeof payload === "string") return payload;
  const p = payload as ApiError;
  return p.detail ?? "Request failed";
}

async function apiFetch<T>(
  path: string,
  {
    method = "GET",
    token,
    jsonBody,
    formData,
  }: {
    method?: string;
    token?: string | null;
    jsonBody?: unknown;
    formData?: FormData;
  },
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const res = await fetch(url, {
    method,
    headers:
      formData || jsonBody
        ? {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(jsonBody ? { "Content-Type": "application/json" } : {}),
          }
        : token
          ? { Authorization: `Bearer ${token}` }
          : undefined,
    body: jsonBody ? JSON.stringify(jsonBody) : formData ? formData : undefined,
  });

  if (!res.ok) {
    if (res.status === 401) {
      clearAccessToken();
      // Dispatch event so active pages can warn about unsaved changes before redirecting
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("auth:expired"));
      }
      throw new Error("Session expired. Please sign in again.");
    }

    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      // ignore
    }
    throw new Error(getErrorMessage(payload));
  }

  return (await res.json()) as T;
}

export async function register(email: string, password: string) {
  return apiFetch<{ access_token: string; token_type: string }>(
    "/auth/register",
    { method: "POST", jsonBody: { email, password } },
  );
}

export async function login(email: string, password: string) {
  return apiFetch<{ access_token: string; token_type: string }>(
    "/auth/login",
    { method: "POST", jsonBody: { email, password } },
  );
}

export async function uploadReceipts(
  files: File[],
  token: string,
): Promise<{ results: { receipt_id: number; processing_status: string }[] }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  return apiFetch<{ results: { receipt_id: number; processing_status: string }[] }>(
    "/receipts/upload",
    { method: "POST", token, formData },
  );
}

export async function getReceipt(receiptId: number, token: string): Promise<ReceiptOut> {
  return apiFetch<ReceiptOut>(`/receipts/${receiptId}`, { token });
}

export async function listReceipts(token: string): Promise<ReceiptOut[]> {
  return apiFetch<ReceiptOut[]>("/receipts", { token });
}

// ── Sample data (load / clear / status) ───────────────────────────────────

export type SampleDataStatus = { loaded: boolean; count: number };

export async function getSampleDataStatus(token: string): Promise<SampleDataStatus> {
  return apiFetch<SampleDataStatus>("/receipts/samples/status", { token });
}

export async function loadSampleData(token: string): Promise<{ already_loaded: boolean; count: number }> {
  return apiFetch<{ already_loaded: boolean; count: number }>(
    "/receipts/samples",
    { method: "POST", token },
  );
}

export async function clearSampleData(token: string): Promise<void> {
  const url = `${API_BASE_URL}/receipts/samples`;
  const res = await fetch(url, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok && res.status !== 204) throw new Error("Could not clear sample data");
}

// ── Server-Sent Events for receipt processing status ──────────────────────
// We use fetch+ReadableStream instead of EventSource because EventSource
// doesn't support custom headers and we need to send the JWT.

export type ReceiptStatusEvent = {
  status: "queued" | "processing" | "parsed" | "confirmed" | "error";
  processing_error?: string | null;
  store_name?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  items_count?: number;
};

export type ReceiptStreamHandle = { close: () => void };

/**
 * Subscribe to a receipt's processing status. Calls onEvent for every status
 * change emitted by the backend. Auto-closes on terminal status, error, or
 * when the returned handle.close() is invoked.
 *
 * Returns an opaque handle whose .close() aborts the underlying fetch.
 */
export function streamReceiptStatus(
  receiptId: number,
  token: string,
  onEvent: (ev: ReceiptStatusEvent) => void,
  onClose?: (reason: "terminal" | "timeout" | "error" | "gone" | "aborted") => void,
): ReceiptStreamHandle {
  const ctrl = new AbortController();
  let closed = false;

  const close = (reason: "terminal" | "timeout" | "error" | "gone" | "aborted") => {
    if (closed) return;
    closed = true;
    try { ctrl.abort(); } catch { /* ignore */ }
    onClose?.(reason);
  };

  (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/receipts/${receiptId}/events`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        close("error");
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          close("terminal");
          return;
        }
        buffer += decoder.decode(value, { stream: true });

        // SSE messages are separated by blank lines.
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const raw of parts) {
          let eventType = "message";
          let data = "";
          for (const line of raw.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.slice(7).trim();
            else if (line.startsWith("data: ")) data += line.slice(6);
            // ":" prefixed = comments / heartbeats, ignored
          }
          if (!data) continue;

          if (eventType === "status") {
            try {
              const parsed = JSON.parse(data) as ReceiptStatusEvent;
              onEvent(parsed);
              if (
                parsed.status === "parsed" ||
                parsed.status === "error" ||
                parsed.status === "confirmed"
              ) {
                close("terminal");
                return;
              }
            } catch { /* malformed event, skip */ }
          } else if (eventType === "timeout") {
            close("timeout");
            return;
          } else if (eventType === "gone") {
            close("gone");
            return;
          }
        }
      }
    } catch (err) {
      if ((err as { name?: string })?.name === "AbortError") close("aborted");
      else close("error");
    }
  })();

  return { close: () => close("aborted") };
}

export async function confirmReceipt(
  receiptId: number,
  payload: { items: { item_name: string; item_price: number; category_id?: number | null; quantity?: number | null; unit_price?: number | null }[] },
  token: string,
): Promise<ReceiptOut> {
  return apiFetch<ReceiptOut>(`/receipts/${receiptId}/confirm`, {
    method: "PATCH",
    token,
    jsonBody: payload,
  });
}

export async function deleteReceipt(receiptId: number, token: string): Promise<void> {
  const url = `${API_BASE_URL}/receipts/${receiptId}`;
  const res = await fetch(url, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok && res.status !== 204) {
    let payload: unknown = null;
    try { payload = await res.json(); } catch { /* ignore */ }
    throw new Error(getErrorMessage(payload));
  }
}

export async function getReceiptImageBlob(receiptId: number, token: string): Promise<string> {
  const url = `${API_BASE_URL}/receipts/${receiptId}/image`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error("Image not available");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function listTransactions(token: string): Promise<{ results: TransactionOut[] }> {
  return apiFetch<{ results: TransactionOut[] }>("/transactions", { token });
}

export type ExportCsvFormat = "generic" | "quickbooks" | "xero";

export async function exportTransactionsCsv(
  token: string,
  format: ExportCsvFormat = "generic",
): Promise<void> {
  const url = `${API_BASE_URL}/transactions/export.csv?format=${encodeURIComponent(format)}`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) {
    let detail = "Export failed";
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `transactions_${format}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export async function listInsights(token: string): Promise<{ results: InsightOut[] }> {
  return apiFetch<{ results: InsightOut[] }>("/insights", { token });
}

export async function livePreviewReceipt(
  blob: Blob,
  token: string,
): Promise<ReceiptOut> {
  const formData = new FormData();
  formData.append("file", blob, "frame.jpg");

  return apiFetch<ReceiptOut>("/receipts/live-preview", {
    method: "POST",
    token,
    formData,
  });
}

export async function listInventory(token: string): Promise<{ results: InventoryItemOut[] }> {
  return apiFetch<{ results: InventoryItemOut[] }>("/inventory", { token });
}

export async function listNeedToBuy(
  token: string,
  leadDays: number = 2,
): Promise<{ results: NeedToBuyItemOut[] }> {
  return apiFetch<{ results: NeedToBuyItemOut[] }>(
    `/recommendations/need-to-buy?lead_days=${encodeURIComponent(String(leadDays))}`,
    { token },
  );
}

export async function listCategories(): Promise<{ id: number; name: string }[]> {
  return apiFetch<{ id: number; name: string }[]>("/meta/categories", {});
}

export async function createReceiptFromFrame(
  blob: Blob,
  token: string,
): Promise<{ receipt_id: number; processing_status: string }> {
  const formData = new FormData();
  formData.append("file", blob, "scan.jpg");

  return apiFetch<{ receipt_id: number; processing_status: string }>(
    "/receipts/from-frame",
    {
      method: "POST",
      token,
      formData,
    },
  );
}

export async function updateProfile(
  currentPassword: string,
  newPassword: string,
  token: string,
): Promise<{ detail: string }> {
  return apiFetch<{ detail: string }>("/auth/profile", {
    method: "PATCH",
    token,
    jsonBody: { current_password: currentPassword, new_password: newPassword },
  });
}

export async function getMe(token: string): Promise<{ id: number; email: string }> {
  return apiFetch<{ id: number; email: string }>("/auth/me", { token });
}

// ── GDPR-style account actions ─────────────────────────────────────────────

/** Download a full JSON dump of the current user's data. */
export async function downloadMyDataExport(token: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/auth/me/export`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Could not export data");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `extasy-export-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** Permanently delete the current user + all owned data. */
export async function deleteMyAccount(token: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/auth/me`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok && res.status !== 204) throw new Error("Could not delete account");
}

// ── New endpoints (live FX, budgets, search, recurring, PDF, households, tax) ──

export type FxRatesResponse = {
  base: string;
  rates: Record<string, number>;
  fetched_at: number;
  source: string;
};
export async function getFxRates(): Promise<FxRatesResponse> {
  return apiFetch<FxRatesResponse>("/fx/rates", {});
}

export type BudgetOut = {
  id: number;
  category_id: number | null;
  category_name: string | null;
  monthly_limit: number;
  currency: string;
  spent: number;
  remaining: number;
  percent: number;
  projected_month_end: number;
  over_budget: boolean;
};
export async function listBudgets(token: string): Promise<{ results: BudgetOut[] }> {
  return apiFetch<{ results: BudgetOut[] }>("/budgets", { token });
}
export async function upsertBudget(
  payload: { category_id: number | null; monthly_limit: number; currency: string },
  token: string,
): Promise<BudgetOut> {
  return apiFetch<BudgetOut>("/budgets", { method: "POST", token, jsonBody: payload });
}
export async function deleteBudget(id: number, token: string): Promise<void> {
  await apiFetch(`/budgets/${id}`, { method: "DELETE", token });
}

export type RecurringItem = {
  product_id: number;
  product_name: string;
  category_name: string | null;
  purchase_count: number;
  avg_interval_days: number;
  interval_cv: number;
  avg_spend: number;
  projected_monthly_spend: number;
  currency: string;
};
export async function listRecurring(
  token: string,
  displayCurrency: string = "BAM",
): Promise<{ results: RecurringItem[]; forecast_monthly_total: number; currency: string }> {
  return apiFetch(`/recommendations/recurring?display_currency=${encodeURIComponent(displayCurrency)}`, { token });
}

export async function searchReceipts(token: string, q: string): Promise<{ results: ReceiptOut[] }> {
  return apiFetch<{ results: ReceiptOut[] }>(
    `/receipts/search?q=${encodeURIComponent(q)}`,
    { token },
  );
}

export async function exportTransactionsPdf(
  token: string,
  opts: { displayCurrency?: string; from?: string; to?: string } = {},
): Promise<void> {
  const params = new URLSearchParams();
  if (opts.displayCurrency) params.set("display_currency", opts.displayCurrency);
  if (opts.from) params.set("from_date", opts.from);
  if (opts.to) params.set("to_date", opts.to);
  const url = `${API_BASE_URL}/transactions/export.pdf?${params.toString()}`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error("PDF export failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "expense_report.pdf";
  a.click();
  URL.revokeObjectURL(a.href);
}

export type HouseholdMember = { user_id: number; email: string; role: string };
export type HouseholdOut = {
  id: number;
  name: string;
  owner_user_id: number;
  invite_token: string;
  members: HouseholdMember[];
};
export async function listHouseholds(token: string): Promise<{ results: HouseholdOut[] }> {
  return apiFetch<{ results: HouseholdOut[] }>("/households", { token });
}
export async function createHousehold(name: string, token: string): Promise<HouseholdOut> {
  return apiFetch<HouseholdOut>("/households", { method: "POST", token, jsonBody: { name } });
}
export async function joinHousehold(inviteToken: string, token: string): Promise<HouseholdOut> {
  return apiFetch<HouseholdOut>("/households/join", { method: "POST", token, jsonBody: { invite_token: inviteToken } });
}

// ── Reconciliation ─────────────────────────────────────────────────────────

export type ReconcileMatch = {
  bank_row: number;
  bank_date: string;
  bank_merchant: string;
  bank_amount: number;
  receipt_id: number;
  receipt_store: string | null;
  receipt_total: number;
  receipt_date: string;
  score: number;
};
export type ReconcileUnmatchedBank = {
  row: number;
  date: string;
  merchant: string;
  amount: number;
};
export type ReconcileUnmatchedReceipt = {
  receipt_id: number;
  store_name: string | null;
  total_amount: number;
  currency: string | null;
  receipt_date: string;
};
export type ReconcileResult = {
  matched: ReconcileMatch[];
  unmatched_bank: ReconcileUnmatchedBank[];
  unmatched_receipts: ReconcileUnmatchedReceipt[];
  stats: {
    bank_rows: number;
    matched: number;
    unmatched_bank: number;
    unmatched_receipts: number;
    match_rate_pct: number;
  };
};

export async function uploadReconcileCsv(
  file: File,
  token: string,
  opts: { amountTolerancePct?: number; dayWindow?: number } = {},
): Promise<ReconcileResult> {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams();
  if (opts.amountTolerancePct != null) params.set("amount_tolerance_pct", String(opts.amountTolerancePct));
  if (opts.dayWindow != null) params.set("day_window", String(opts.dayWindow));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<ReconcileResult>(`/reconcile/upload${qs}`, { method: "POST", token, formData });
}

export function reconcileSampleCsvUrl(token: string): string {
  // The endpoint requires auth — we can't link to it directly, so the page
  // fetches it via JS. Kept here for completeness.
  void token;
  return `${API_BASE_URL}/reconcile/sample.csv`;
}

export async function downloadReconcileSample(token: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/reconcile/sample.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Could not load sample CSV");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "bank_sample.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

// ── Billing ────────────────────────────────────────────────────────────────

export type PlanInfo = {
  id: "free" | "pro" | "business";
  name: string;
  price_cents: number;
  receipts_per_month: number | null;
  features: string[];
};
export type PlansResponse = {
  currency: string;
  plans: PlanInfo[];
  configured: boolean;
  /** Days of free trial offered on first checkout (0 = no trial) */
  trial_days?: number;
};
export async function listPlans(): Promise<PlansResponse> {
  return apiFetch<PlansResponse>("/billing/plans", {});
}

export type BillingMe = {
  plan: "free" | "pro" | "business";
  status: string;
  current_period_end: string | null;
  usage: {
    receipts_used: number;
    receipts_quota: number;       // 0 = unlimited
    percent: number;
  };
};
export async function getMyBilling(token: string): Promise<BillingMe> {
  return apiFetch<BillingMe>("/billing/me", { token });
}

export async function startCheckout(plan: "pro" | "business", token: string): Promise<{ checkout_url: string }> {
  return apiFetch<{ checkout_url: string }>("/billing/checkout", {
    method: "POST",
    token,
    jsonBody: { plan },
  });
}

export async function openCustomerPortal(token: string): Promise<{ portal_url: string }> {
  return apiFetch<{ portal_url: string }>("/billing/portal", { method: "POST", token });
}
