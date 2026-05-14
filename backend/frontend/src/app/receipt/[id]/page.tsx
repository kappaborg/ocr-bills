"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import { confirmReceipt, getReceipt, listCategories } from "@/lib/api";
import type { ReceiptOut } from "@/lib/types";
import { formatReceiptDate } from "@/lib/format";

type Category = { id: number; name: string };

type EditItem = {
  _key: number;
  item_name: string;
  item_price: number;
  category_id: number | null;
  quantity: number | null;
  unit_price: number | null;
};

let _keyCounter = 0;
function makeKey() {
  return ++_keyCounter;
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    parsed: "bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/30",
    confirmed: "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30",
    error: "bg-red-500/20 text-red-300 ring-1 ring-red-500/30",
    processing: "bg-amber-500/20 text-amber-200 ring-1 ring-amber-500/30",
    queued: "bg-slate-500/20 text-slate-300 ring-1 ring-white/10",
  };
  return map[status] ?? map.queued;
}

export default function ReceiptReviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const receiptId = useMemo(() => Number(params.id), [params.id]);
  const token = getAccessToken();

  const [receipt, setReceipt] = useState<ReceiptOut | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [editItems, setEditItems] = useState<EditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingTimeout, setProcessingTimeout] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load receipt (with retry until processed) + categories in parallel.
  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }

    let cancelled = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const [cats] = await Promise.all([listCategories()]);
        if (!cancelled) setCategories(cats);

        // Poll up to 45 times × 800 ms ≈ 36 s.  Large images with many language packs
        // can take 20–30 s on a mid-range laptop; 36 s gives a comfortable margin.
        const MAX_POLLS = 45;
        let timedOut = true;
        for (let i = 0; i < MAX_POLLS; i++) {
          const r = await getReceipt(receiptId, token);
          if (cancelled) return;
          setReceipt(r);

          const st = r.processing_status;
          if (st === "parsed" || st === "confirmed" || st === "error") {
            timedOut = false;
            setEditItems(
              r.items.map((it) => ({
                _key: makeKey(),
                item_name: it.item_name,
                item_price: it.item_price,
                category_id: it.category_id ?? null,
                quantity: it.quantity ?? null,
                unit_price: it.unit_price ?? null,
              }))
            );
            break;
          }
          await new Promise((res) => setTimeout(res, 800));
        }
        if (timedOut && !cancelled) setProcessingTimeout(true);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    run();
    return () => { cancelled = true; };
  }, [receiptId, router, token]);

  // ── Item editing helpers ──────────────────────────────────────────────────

  const updateItem = (key: number, patch: Partial<Omit<EditItem, "_key">>) => {
    setEditItems((prev) =>
      prev.map((it) => (it._key === key ? { ...it, ...patch } : it))
    );
  };

  const deleteItem = (key: number) => {
    setEditItems((prev) => prev.filter((it) => it._key !== key));
  };

  const addItem = () => {
    setEditItems((prev) => [
      ...prev,
      { _key: makeKey(), item_name: "", item_price: 0, category_id: null, quantity: null, unit_price: null },
    ]);
  };

  // ── Confirm ───────────────────────────────────────────────────────────────

  const canConfirm =
    receipt !== null &&
    receipt.processing_status !== "queued" &&
    receipt.processing_status !== "processing" &&
    receipt.processing_status !== "confirmed";

  const onConfirm = async () => {
    if (!token || !receipt || !canConfirm) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        items: editItems
          .filter((it) => it.item_name.trim().length >= 2 && it.item_price > 0)
          .map((it) => ({
            item_name: it.item_name.trim(),
            item_price: it.item_price,
            category_id: it.category_id ?? null,
            quantity: it.quantity ?? null,
            unit_price: it.unit_price ?? null,
          })),
      };

      const updated = await confirmReceipt(receiptId, payload, token);
      setReceipt(updated);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
            Review
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
            Line items
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Receipt #{receiptId} · Edit items, then confirm to save
          </p>
        </div>
        <button
          type="button"
          onClick={() => router.push("/upload")}
          className="self-start rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/10"
        >
          + Add receipt
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200"
        >
          {error}
        </div>
      )}

      {processingTimeout && !error && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-sm text-amber-200"
        >
          OCR is taking longer than expected. The image may be very large or the server is busy.
          Try refreshing this page in a few seconds, or add items manually below.
        </div>
      )}

      {loading ? (
        <div className="glass-panel flex flex-col items-center justify-center gap-3 px-8 py-16 text-center">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
          <p className="text-sm text-slate-400">Reading your receipt…</p>
        </div>
      ) : !receipt ? (
        <p className="text-sm text-slate-400">Receipt not found.</p>
      ) : (
        <div className="space-y-6">
          {/* Header card */}
          <section className="glass-panel overflow-hidden p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${statusBadge(receipt.processing_status)}`}
              >
                {receipt.processing_status}
              </span>
              {receipt.detected_language && (
                <span className="text-xs text-slate-500">
                  Language ·{" "}
                  <span className="font-mono text-slate-300">{receipt.detected_language}</span>
                </span>
              )}
            </div>

            {receipt.processing_error && (
              <p className="mt-3 text-sm text-red-300">{receipt.processing_error}</p>
            )}

            <dl className="mt-6 grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl bg-slate-950/50 p-4 ring-1 ring-white/5">
                <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  Merchant
                </dt>
                <dd className="mt-1 text-sm font-medium text-slate-100">
                  {receipt.store_name ?? "—"}
                </dd>
              </div>
              <div className="rounded-xl bg-slate-950/50 p-4 ring-1 ring-white/5">
                <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  Date
                </dt>
                <dd className="mt-1 text-sm font-medium text-slate-100">
                  {formatReceiptDate(receipt.receipt_date ?? null)}
                </dd>
              </div>
              <div className="rounded-xl bg-slate-950/50 p-4 ring-1 ring-white/5">
                <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  Total
                </dt>
                <dd className="mt-1 font-mono text-lg font-semibold tabular-nums text-cyan-300">
                  {receipt.total_amount != null ? receipt.total_amount.toFixed(2) : "—"}{" "}
                  <span className="text-sm font-normal text-slate-400">
                    {receipt.currency ?? ""}
                  </span>
                </dd>
              </div>
            </dl>
          </section>

          {/* Editable items */}
          <section className="glass-panel p-5 sm:p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-50">Items</h2>
                <p className="mt-0.5 text-sm text-slate-500">
                  Edit names, prices or categories. Delete junk rows.
                </p>
              </div>
              <button
                type="button"
                onClick={addItem}
                className="shrink-0 rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10"
              >
                + Add item
              </button>
            </div>

            {editItems.length === 0 ? (
              <div className="mt-6 rounded-xl border border-dashed border-white/15 px-6 py-8 text-center">
                <p className="text-sm text-slate-400">
                  No items detected. Use &ldquo;+ Add item&rdquo; to enter them manually.
                </p>
              </div>
            ) : (
              <ul className="mt-5 space-y-3">
                {editItems.map((it) => (
                  <li
                    key={it._key}
                    className="rounded-xl border border-white/10 bg-slate-950/60 p-3 ring-1 ring-white/5"
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                      {/* Name */}
                      <input
                        type="text"
                        value={it.item_name}
                        onChange={(e) => updateItem(it._key, { item_name: e.target.value })}
                        placeholder="Item name"
                        className="min-w-0 flex-1 rounded-lg border border-white/10 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
                      />

                      {/* Price */}
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={it.item_price || ""}
                        onChange={(e) =>
                          updateItem(it._key, { item_price: parseFloat(e.target.value) || 0 })
                        }
                        placeholder="0.00"
                        className="w-24 shrink-0 rounded-lg border border-white/10 bg-slate-900/80 px-3 py-1.5 font-mono text-sm text-emerald-300 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
                      />

                      {/* Category */}
                      <select
                        value={it.category_id ?? ""}
                        onChange={(e) =>
                          updateItem(it._key, {
                            category_id: e.target.value ? Number(e.target.value) : null,
                          })
                        }
                        className="w-36 shrink-0 rounded-lg border border-white/10 bg-slate-900/80 px-2 py-1.5 text-xs text-slate-300 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
                      >
                        <option value="">Category…</option>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>

                      {/* Delete */}
                      <button
                        type="button"
                        onClick={() => deleteItem(it._key)}
                        className="shrink-0 rounded-lg p-1.5 text-slate-500 transition hover:bg-red-900/40 hover:text-red-300"
                        aria-label="Delete item"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          viewBox="0 0 16 16"
                          fill="currentColor"
                          className="h-4 w-4"
                        >
                          <path
                            fillRule="evenodd"
                            d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5A.75.75 0 0 1 9.95 6Z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="button"
                disabled={submitting || !canConfirm}
                onClick={onConfirm}
                className="inline-flex flex-1 items-center justify-center rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-5 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting
                  ? "Saving…"
                  : receipt.processing_status === "confirmed"
                  ? "Already saved"
                  : "Confirm & save"}
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => router.replace("/dashboard")}
                className="rounded-xl border border-white/15 bg-white/5 px-5 py-3 text-sm font-medium text-slate-200 hover:bg-white/10 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>

            {receipt.processing_status === "error" && (
              <p className="mt-3 text-xs text-slate-500">
                OCR failed on this receipt. Add items manually above then confirm.
              </p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
