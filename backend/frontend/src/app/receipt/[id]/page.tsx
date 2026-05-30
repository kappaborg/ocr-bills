"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import {
  confirmReceipt,
  getReceipt,
  getReceiptImageBlob,
  listCategories,
  streamReceiptStatus,
} from "@/lib/api";
import type { ReceiptOut } from "@/lib/types";
import { formatCurrency, formatReceiptDate } from "@/lib/format";

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
function makeKey() { return ++_keyCounter; }

// Module-level category cache — categories never change, no need to re-fetch
let _cachedCategories: Category[] | null = null;
async function getCachedCategories(): Promise<Category[]> {
  if (_cachedCategories) return _cachedCategories;
  _cachedCategories = await listCategories();
  return _cachedCategories;
}

const MAX_POLL_SECONDS = 36;
const POLL_INTERVAL_MS = 800;

function statusBadge(status: string) {
  const map: Record<string, string> = {
    parsed:     "bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/30",
    confirmed:  "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30",
    error:      "bg-red-500/20 text-red-300 ring-1 ring-red-500/30",
    processing: "bg-amber-500/20 text-amber-200 ring-1 ring-amber-500/30",
    queued:     "bg-slate-500/20 text-slate-300 ring-1 ring-white/10",
  };
  return map[status] ?? map.queued;
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    queued:     "Waiting…",
    processing: "Scanning…",
    parsed:     "Ready to review",
    confirmed:  "Saved",
    error:      "Scan failed",
  };
  return map[status] ?? status;
}

// Narration shown while OCR is running. Picks one line based on elapsed
// seconds — gives users a sense the system is alive even without granular
// progress signals from the backend.
function progressNarration(status: string, elapsedSec: number): string {
  if (status === "queued") return "Just opened your receipt — about to start";
  if (status !== "processing") return "";
  if (elapsedSec < 3)   return "Reading the image…";
  if (elapsedSec < 7)   return "Detecting text in any language…";
  if (elapsedSec < 14)  return "Extracting line items and totals…";
  if (elapsedSec < 22)  return "Almost done…";
  return "Taking a little longer than usual — hold on";
}

export default function ReceiptReviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const receiptId = useMemo(() => {
    const n = parseInt(params.id, 10);
    return isNaN(n) ? null : n;
  }, [params.id]);
  const token = getAccessToken();

  const [receipt, setReceipt] = useState<ReceiptOut | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [editItems, setEditItems] = useState<EditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [processingTimeout, setProcessingTimeout] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [pendingDeleteKey, setPendingDeleteKey] = useState<number | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageOpen, setImageOpen] = useState(false);
  const imageUrlRef = useRef<string | null>(null);

  // Listen for session expiry so user can save edits before being redirected
  useEffect(() => {
    const onExpired = () => setSessionExpired(true);
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  // Redirect if invalid ID or no token
  useEffect(() => {
    if (!receiptId) { router.replace("/dashboard"); return; }
    if (!token) { router.replace("/login"); return; }
  }, [receiptId, token, router]);

  // Elapsed timer while loading
  useEffect(() => {
    if (!loading) { setElapsed(0); return; }
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [loading]);

  // Load receipt + subscribe to status stream (SSE), with polling fallback.
  useEffect(() => {
    if (!token || !receiptId) return;

    let cancelled = false;
    let streamHandle: { close: () => void } | null = null;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    const applyItems = (r: ReceiptOut) => {
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
    };

    const refetchAndFinish = async () => {
      try {
        const r = await getReceipt(receiptId, token);
        if (cancelled) return;
        setReceipt(r);
        if (r.processing_status === "parsed" || r.processing_status === "confirmed" || r.processing_status === "error") {
          applyItems(r);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      }
    };

    const pollFallback = async () => {
      const maxPolls = Math.ceil((MAX_POLL_SECONDS * 1000) / POLL_INTERVAL_MS);
      let timedOut = true;
      for (let i = 0; i < maxPolls; i++) {
        if (cancelled) return;
        try {
          const r = await getReceipt(receiptId, token);
          if (cancelled) return;
          setReceipt(r);
          if (r.processing_status === "parsed" || r.processing_status === "confirmed" || r.processing_status === "error") {
            applyItems(r);
            timedOut = false;
            setLoading(false);
            break;
          }
        } catch {
          /* transient error — keep polling */
        }
        await new Promise((res) => { pollTimer = setTimeout(res, POLL_INTERVAL_MS); });
      }
      if (timedOut && !cancelled) {
        setProcessingTimeout(true);
        setLoading(false);
      }
    };

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        // Categories load alongside; doesn't block status subscription.
        getCachedCategories().then((cats) => { if (!cancelled) setCategories(cats); }).catch(() => {});

        // 1. Fetch initial state once so we have something to render immediately.
        const initial = await getReceipt(receiptId, token);
        if (cancelled) return;
        setReceipt(initial);
        if (
          initial.processing_status === "parsed" ||
          initial.processing_status === "confirmed" ||
          initial.processing_status === "error"
        ) {
          applyItems(initial);
          setLoading(false);
          return;  // Already terminal — no stream needed
        }

        // 2. Subscribe to SSE for status transitions.
        streamHandle = streamReceiptStatus(
          receiptId,
          token,
          (ev) => {
            if (cancelled) return;
            // Merge the lightweight status event into our receipt object so the
            // UI updates immediately even before the full refetch lands.
            setReceipt((prev) => prev ? {
              ...prev,
              processing_status: ev.status,
              processing_error: ev.processing_error ?? prev.processing_error,
              store_name: ev.store_name ?? prev.store_name,
              total_amount: ev.total_amount ?? prev.total_amount,
              currency: ev.currency ?? prev.currency,
            } : prev);

            // On terminal status, refetch full payload (items) and stop loading.
            if (ev.status === "parsed" || ev.status === "confirmed" || ev.status === "error") {
              refetchAndFinish();
            }
          },
          (reason) => {
            if (cancelled) return;
            // Fall back to polling if SSE failed before reaching terminal state.
            if (reason === "error" || reason === "timeout") {
              pollFallback();
            }
          },
        );
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
          setLoading(false);
        }
      }
    };

    run();
    return () => {
      cancelled = true;
      if (streamHandle) streamHandle.close();
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [receiptId, token]);

  // Load receipt image after receipt is known
  useEffect(() => {
    if (!receipt || !token || !receiptId) return;
    let alive = true;
    getReceiptImageBlob(receiptId, token)
      .then((url) => {
        if (!alive) { URL.revokeObjectURL(url); return; }
        imageUrlRef.current = url;
        setImageUrl(url);
      })
      .catch(() => { /* image unavailable is fine */ });
    return () => {
      alive = false;
      if (imageUrlRef.current) {
        URL.revokeObjectURL(imageUrlRef.current);
        imageUrlRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [receipt?.id, token, receiptId]); // receipt.id is the only meaningful dep; full receipt object would re-run on every render

  // ── Item editing helpers ──────────────────────────────────────────────────

  const updateItem = (key: number, patch: Partial<Omit<EditItem, "_key">>) => {
    setEditItems((prev) =>
      prev.map((it) => (it._key === key ? { ...it, ...patch } : it))
    );
  };

  const deleteItem = (key: number) => {
    setEditItems((prev) => prev.filter((it) => it._key !== key));
    setPendingDeleteKey(null);
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
    if (!token || !receipt || !canConfirm || !receiptId) return;
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

  // ── Loading message based on current status + elapsed time ────────────────

  const currentStatus = receipt?.processing_status ?? "queued";
  // Status-aware narration. Falls back to elapsed-time messaging when we
  // don't have a live SSE update yet.
  const loadingMessage =
    progressNarration(currentStatus, elapsed) ||
    (elapsed < 15
      ? `Still working… (${elapsed}s)`
      : `This is taking longer than usual (${elapsed}s)`);

  const progressPct = Math.min((elapsed / MAX_POLL_SECONDS) * 100, 95);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      {/* Session expired modal */}
      {sessionExpired && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm px-4">
          <div className="glass-panel w-full max-w-sm p-6 text-center">
            <p className="text-lg font-semibold text-slate-50">Session expired</p>
            <p className="mt-2 text-sm text-slate-400">
              Your session has expired. Any unsaved changes may be lost.
            </p>
            <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-center">
              <a
                href="/login"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:brightness-110"
              >
                Sign in again (new tab)
              </a>
              <button
                type="button"
                onClick={() => setSessionExpired(false)}
                className="rounded-xl border border-white/15 bg-white/5 px-5 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/10"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

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
        <div className="glass-panel flex flex-col items-center justify-center gap-4 px-8 py-16 text-center">
          {/* Status chip + live pulse — communicates that we're actively
              listening to the backend, not just spinning blindly. */}
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400/60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${statusBadge(currentStatus)}`}
            >
              {statusLabel(currentStatus)}
            </span>
          </div>
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
          <p className="text-sm text-slate-300">{loadingMessage}</p>
          <div className="w-48 overflow-hidden rounded-full bg-white/10 h-1.5">
            <div
              className="h-full rounded-full bg-cyan-400 transition-all duration-1000"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-500">Live updates from the OCR pipeline</p>
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
                {statusLabel(receipt.processing_status)}
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
                  {formatCurrency(receipt.total_amount, receipt.currency)}
                </dd>
              </div>
            </dl>

            {/* Original image viewer */}
            {imageUrl && (
              <div className="mt-5">
                <button
                  type="button"
                  onClick={() => setImageOpen((o) => !o)}
                  className="flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <svg className={`h-3.5 w-3.5 transition-transform ${imageOpen ? "rotate-90" : ""}`} viewBox="0 0 16 16" fill="currentColor">
                    <path d="M6 3.25l5.5 4.75-5.5 4.75V3.25z"/>
                  </svg>
                  {imageOpen ? "Hide original image" : "View original image"}
                </button>
                {imageOpen && (
                  <div className="mt-3 overflow-hidden rounded-xl border border-white/10">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imageUrl}
                      alt="Original receipt"
                      loading="lazy"
                      className="w-full object-contain max-h-[60vh]"
                    />
                  </div>
                )}
              </div>
            )}
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

                      {/* Delete with inline confirm */}
                      {pendingDeleteKey === it._key ? (
                        <div className="flex shrink-0 items-center gap-1">
                          <button
                            type="button"
                            onClick={() => deleteItem(it._key)}
                            className="rounded-lg px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-900/40"
                          >
                            Delete
                          </button>
                          <button
                            type="button"
                            onClick={() => setPendingDeleteKey(null)}
                            className="rounded-lg px-2 py-1 text-xs font-medium text-slate-400 hover:bg-white/5"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setPendingDeleteKey(it._key)}
                          className="shrink-0 rounded-lg p-1.5 text-slate-500 transition hover:bg-red-900/40 hover:text-red-300"
                          aria-label="Delete item"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
                            <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5A.75.75 0 0 1 9.95 6Z" clipRule="evenodd" />
                          </svg>
                        </button>
                      )}
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
