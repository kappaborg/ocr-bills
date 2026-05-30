"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import {
  confirmReceipt,
  deleteReceipt,
  getReceiptImageBlob,
  listReceipts,
} from "@/lib/api";
import type { ReceiptOut } from "@/lib/types";
import { formatCurrency, formatTimeAgo } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useConfirm } from "@/components/ConfirmDialog";

// Inbox shows receipts that finished OCR but haven't been confirmed yet.
// Power users with 50+ receipts/month will live here.

type InboxKey = "j" | "k" | "Enter" | "e" | "x" | "?";

const SHORTCUTS: { key: InboxKey | string; label: string }[] = [
  { key: "j / ↓", label: "next receipt" },
  { key: "k / ↑", label: "previous receipt" },
  { key: "Enter", label: "confirm as-is" },
  { key: "e", label: "edit on detail page" },
  { key: "x", label: "delete receipt" },
  { key: "?", label: "toggle this help" },
];

export default function InboxPage() {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();

  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setToken(getAccessToken());
    setMounted(true);
  }, []);

  const [allReceipts, setAllReceipts] = useState<ReceiptOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [helpOpen, setHelpOpen] = useState(false);

  // The current selection cursor — index into `pending`
  const [cursor, setCursor] = useState(0);
  // Per-receipt action busy state so we can disable shortcuts mid-flight
  const [busyId, setBusyId] = useState<number | null>(null);
  // Receipt image URL cache, keyed by receipt_id
  const imageUrlsRef = useRef<Map<number, string>>(new Map());
  const [currentImageUrl, setCurrentImageUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!mounted) return;
    if (!token) { router.replace("/login"); return; }
    setLoading(true);
    listReceipts(token)
      .then((rs) => setAllReceipts(rs))
      .catch((e) => toast.push(e instanceof Error ? e.message : "Failed to load", { kind: "error" }))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, token, router]);

  // Pending = parsed (OCR done) but not yet confirmed.
  const pending = useMemo(
    () => allReceipts.filter((r) => r.processing_status === "parsed"),
    [allReceipts],
  );
  const total = allReceipts.length;
  const reviewed = total - pending.length;

  // Clamp cursor when the list shrinks
  useEffect(() => {
    if (cursor >= pending.length && pending.length > 0) setCursor(pending.length - 1);
  }, [pending.length, cursor]);

  const current = pending[cursor] ?? null;

  // Load image for the currently-selected receipt
  useEffect(() => {
    if (!current || !token) {
      setCurrentImageUrl(null);
      return;
    }
    const cached = imageUrlsRef.current.get(current.id);
    if (cached) {
      setCurrentImageUrl(cached);
      return;
    }
    let alive = true;
    getReceiptImageBlob(current.id, token)
      .then((url) => {
        if (!alive) { URL.revokeObjectURL(url); return; }
        imageUrlsRef.current.set(current.id, url);
        setCurrentImageUrl(url);
      })
      .catch(() => setCurrentImageUrl(null));
    return () => { alive = false; };
  }, [current, token]);

  // Cleanup all image blob URLs on unmount
  useEffect(() => {
    const urls = imageUrlsRef.current;
    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u));
      urls.clear();
    };
  }, []);

  // ── Actions ───────────────────────────────────────────────────────────

  const confirmCurrent = useCallback(async () => {
    if (!current || !token || busyId === current.id) return;
    setBusyId(current.id);
    try {
      const updated = await confirmReceipt(
        current.id,
        {
          items: current.items.map((it) => ({
            item_name: it.item_name,
            item_price: it.item_price,
            category_id: it.category_id ?? null,
            quantity: it.quantity ?? null,
            unit_price: it.unit_price ?? null,
          })),
        },
        token,
      );
      // Replace the receipt in our local list so it disappears from `pending`
      setAllReceipts((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      toast.push(`Confirmed: ${updated.store_name ?? `Receipt #${updated.id}`}`, { kind: "success" });
      // Cursor naturally moves to the next pending one because the list shrinks
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Confirm failed";
      toast.push(msg, { kind: "error" });
    } finally {
      setBusyId(null);
    }
  }, [current, token, busyId, toast]);

  const skipToDetail = useCallback(() => {
    if (!current) return;
    router.push(`/receipt/${current.id}`);
  }, [current, router]);

  const deleteCurrent = useCallback(async () => {
    if (!current || !token || busyId === current.id) return;
    const ok = await confirm({
      title: "Delete this receipt?",
      body: `${current.store_name ?? "No merchant"} — ${current.items.length} item${current.items.length === 1 ? "" : "s"}. This cannot be undone.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setBusyId(current.id);
    try {
      await deleteReceipt(current.id, token);
      setAllReceipts((prev) => prev.filter((r) => r.id !== current.id));
      toast.push("Receipt deleted", { kind: "info" });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      toast.push(msg, { kind: "error" });
    } finally {
      setBusyId(null);
    }
  }, [current, token, busyId, confirm, toast]);

  // ── Keyboard ──────────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore shortcuts while typing in inputs
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      switch (e.key) {
        case "j":
        case "ArrowDown":
          e.preventDefault();
          setCursor((c) => Math.min(c + 1, Math.max(0, pending.length - 1)));
          break;
        case "k":
        case "ArrowUp":
          e.preventDefault();
          setCursor((c) => Math.max(0, c - 1));
          break;
        case "Enter":
          e.preventDefault();
          confirmCurrent();
          break;
        case "e":
          e.preventDefault();
          skipToDetail();
          break;
        case "x":
          e.preventDefault();
          deleteCurrent();
          break;
        case "?":
          e.preventDefault();
          setHelpOpen((v) => !v);
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [pending.length, confirmCurrent, skipToDetail, deleteCurrent]);

  // ── Render ────────────────────────────────────────────────────────────

  if (!mounted) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="h-64 animate-pulse rounded-2xl bg-white/5" />
      </main>
    );
  }
  if (!token) return null;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">Inbox</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
            Review receipts
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Keyboard-first batch confirm. Press <kbd className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-xs">?</kbd> for shortcuts.
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm">
          <span className="font-mono text-cyan-300">{reviewed}</span>
          <span className="text-slate-500"> / </span>
          <span className="font-mono text-slate-300">{total}</span>
          <span className="ml-1 text-xs text-slate-500">reviewed</span>
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
          <div className="h-96 animate-pulse rounded-2xl bg-white/5" />
          <div className="h-96 animate-pulse rounded-2xl bg-white/5" />
        </div>
      ) : pending.length === 0 ? (
        <section className="glass-panel p-10 text-center">
          <p className="text-3xl">📭</p>
          <h2 className="mt-3 text-lg font-semibold text-slate-100">Inbox zero</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
            No receipts waiting for review. Upload more to see them here, or head back to
            the dashboard.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={() => router.push("/upload")}
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
            >
              Upload more
            </button>
            <button
              type="button"
              onClick={() => router.push("/dashboard")}
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 hover:bg-white/10"
            >
              Dashboard
            </button>
          </div>
        </section>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[260px_1fr_1fr]">
          {/* ── Left rail: pending list ─────────────────────────────────── */}
          <aside className="glass-panel max-h-[70vh] overflow-y-auto p-2">
            <ul className="space-y-1">
              {pending.map((r, i) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => setCursor(i)}
                    className={`block w-full rounded-lg px-3 py-2 text-left transition ${
                      i === cursor
                        ? "bg-cyan-500/15 ring-1 ring-cyan-500/40"
                        : "hover:bg-white/5"
                    }`}
                  >
                    <p className="truncate text-sm font-medium text-slate-100">
                      {r.store_name ?? `Receipt #${r.id}`}
                    </p>
                    <p className="mt-0.5 truncate text-[11px] text-slate-500">
                      {formatTimeAgo(r.receipt_date ?? null)} ·{" "}
                      {r.items.length} item{r.items.length === 1 ? "" : "s"}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          {/* ── Middle: image preview ────────────────────────────────────── */}
          <section className="glass-panel flex flex-col p-4">
            {currentImageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={currentImageUrl}
                alt="Receipt"
                className="mx-auto max-h-[70vh] w-full rounded-xl object-contain"
              />
            ) : (
              <div className="flex flex-1 items-center justify-center rounded-xl bg-white/5 py-16 text-sm text-slate-500">
                {current ? "Loading image…" : "Pick a receipt"}
              </div>
            )}
          </section>

          {/* ── Right: items + action buttons ────────────────────────────── */}
          <section className="glass-panel flex flex-col p-4">
            {current ? (
              <>
                <div className="flex flex-wrap items-baseline justify-between gap-2 pb-3">
                  <h2 className="text-base font-semibold text-slate-100">
                    {current.store_name ?? `Receipt #${current.id}`}
                  </h2>
                  <p className="font-mono text-lg tabular-nums text-cyan-300">
                    {formatCurrency(current.total_amount, current.currency)}
                  </p>
                </div>
                <p className="text-[11px] text-slate-500">
                  <span title={current.receipt_date ?? ""}>
                    {formatTimeAgo(current.receipt_date ?? null)}
                  </span> ·{" "}
                  {current.detected_language ?? "—"} ·{" "}
                  {current.items.length} item{current.items.length === 1 ? "" : "s"}
                </p>

                <ul className="mt-3 flex-1 space-y-1 overflow-y-auto pr-1">
                  {current.items.length === 0 ? (
                    <li className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-center text-xs text-slate-500">
                      No items detected — press <kbd className="rounded bg-white/10 px-1 py-0.5 font-mono">e</kbd> to add manually
                    </li>
                  ) : current.items.map((it) => (
                    <li
                      key={it.id}
                      className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-slate-950/50 px-3 py-2"
                    >
                      <span className="truncate text-sm text-slate-200">{it.item_name}</span>
                      <span className="shrink-0 font-mono text-xs tabular-nums text-emerald-300">
                        {formatCurrency(it.item_price, current.currency)}
                      </span>
                    </li>
                  ))}
                </ul>

                <div className="mt-3 flex flex-wrap gap-2 border-t border-white/10 pt-3">
                  <button
                    type="button"
                    disabled={busyId === current.id}
                    onClick={confirmCurrent}
                    className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110 disabled:opacity-50"
                  >
                    {busyId === current.id ? "Confirming…" : "Confirm ↵"}
                  </button>
                  <button
                    type="button"
                    onClick={skipToDetail}
                    className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
                  >
                    Edit (e)
                  </button>
                  <button
                    type="button"
                    disabled={busyId === current.id}
                    onClick={deleteCurrent}
                    className="rounded-xl border border-red-500/30 bg-red-950/30 px-4 py-2 text-sm font-medium text-red-300 hover:bg-red-950/50 disabled:opacity-50"
                    title="Delete (x)"
                  >
                    Delete
                  </button>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">No receipt selected</p>
            )}
          </section>
        </div>
      )}

      {/* Floating help panel — opens with `?` */}
      {helpOpen && (
        <div
          role="dialog"
          className="fixed bottom-6 right-6 z-50 max-w-xs rounded-2xl border border-white/15 bg-slate-950/95 p-4 text-sm shadow-2xl backdrop-blur"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs font-medium uppercase tracking-wider text-cyan-400/90">Shortcuts</p>
            <button onClick={() => setHelpOpen(false)} className="text-slate-500 hover:text-slate-300" aria-label="Close help">×</button>
          </div>
          <ul className="space-y-1.5 text-xs">
            {SHORTCUTS.map((s) => (
              <li key={s.key} className="flex items-center justify-between gap-3">
                <kbd className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[11px] text-slate-200">{s.key}</kbd>
                <span className="text-slate-400">{s.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
