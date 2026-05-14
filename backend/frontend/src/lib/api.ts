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

export async function exportTransactionsCsv(token: string): Promise<void> {
  const url = `${API_BASE_URL}/transactions/export.csv`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "transactions.csv";
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
