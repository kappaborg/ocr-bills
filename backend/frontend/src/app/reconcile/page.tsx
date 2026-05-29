"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getAccessToken } from "@/lib/auth";
import {
  downloadReconcileSample,
  getMyBilling,
  uploadReconcileCsv,
  type BillingMe,
  type ReconcileResult,
} from "@/lib/api";
import { formatCurrency } from "@/lib/format";

export default function ReconcilePage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [billing, setBilling] = useState<BillingMe | null>(null);

  useEffect(() => {
    setToken(getAccessToken());
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    getMyBilling(token).then(setBilling).catch(() => {});
  }, [mounted, token, router]);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [tolerance, setTolerance] = useState(5);
  const [dayWindow, setDayWindow] = useState(2);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ReconcileResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f && f.name.toLowerCase().endsWith(".csv")) {
      setFile(f);
      setError(null);
      setResult(null);
    } else {
      setError("Please drop a .csv file.");
    }
  };

  const handleSubmit = async () => {
    if (!file || !token) return;
    setUploading(true);
    setError(null);
    try {
      const r = await uploadReconcileCsv(file, token, {
        amountTolerancePct: tolerance,
        dayWindow,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reconciliation failed");
    } finally {
      setUploading(false);
    }
  };

  if (!mounted) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="h-40 animate-pulse rounded-2xl bg-white/5" />
      </main>
    );
  }
  if (!token) return null;

  // Hold the page back until the plan is known — otherwise free users would
  // see the upload form flash before the gated card replaces it.
  if (billing === null) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="space-y-4">
          <div className="h-8 w-40 animate-pulse rounded-xl bg-white/5" />
          <div className="h-40 animate-pulse rounded-2xl bg-white/5" />
        </div>
      </main>
    );
  }

  // Plan check up-front so we don't show the upload UI to users who'd just get 402.
  if (billing.plan !== "business") {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12 text-center">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">Reconcile</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-50">Business plan required</h1>
        <p className="mx-auto mt-3 max-w-md text-sm text-slate-400">
          Bank reconciliation matches your receipts against your bank statement to surface
          missing receipts and orphan charges. Available on the Business plan.
        </p>
        <Link
          href="/pricing"
          className="mt-6 inline-block rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
        >
          See plans
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">Reconcile</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
        Match bank statement to receipts
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        Upload your bank CSV (date, merchant, amount). We&apos;ll find which charges have
        a receipt and which don&apos;t — and which receipts are missing from your statement.
      </p>

      {error && (
        <div role="alert" className="mt-4 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {/* Drop zone */}
      <section className="mt-8 glass-panel p-5 sm:p-6">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragging ? "border-cyan-400 bg-cyan-500/5" : "border-white/15 hover:border-white/30"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              setError(null);
              setResult(null);
            }}
          />
          {file ? (
            <div>
              <p className="text-sm font-medium text-slate-100">{file.name}</p>
              <p className="mt-1 text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB · click or drop to replace</p>
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-slate-200">Drop a CSV here or click to choose</p>
              <p className="mt-1 text-xs text-slate-500">Expected columns: date, merchant, amount</p>
            </div>
          )}
        </div>

        <div className="mt-5 grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs uppercase tracking-wider text-slate-500">Amount tolerance</span>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={tolerance}
                min={0}
                max={20}
                step={0.5}
                onChange={(e) => setTolerance(parseFloat(e.target.value) || 0)}
                className="w-20 rounded-lg border border-white/10 bg-slate-950/60 px-2 py-1 text-sm text-slate-100 focus:border-cyan-500/50 focus:outline-none"
              />
              <span className="text-xs text-slate-500">% (default 5%)</span>
            </div>
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-wider text-slate-500">Date window</span>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={dayWindow}
                min={0}
                max={14}
                step={1}
                onChange={(e) => setDayWindow(parseInt(e.target.value) || 0)}
                className="w-20 rounded-lg border border-white/10 bg-slate-950/60 px-2 py-1 text-sm text-slate-100 focus:border-cyan-500/50 focus:outline-none"
              />
              <span className="text-xs text-slate-500">±days (default 2)</span>
            </div>
          </label>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={!file || uploading}
            onClick={handleSubmit}
            className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110 disabled:opacity-40"
          >
            {uploading ? "Matching…" : "Reconcile"}
          </button>
          <button
            type="button"
            onClick={() => downloadReconcileSample(token!).catch((e) => setError(e.message))}
            className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/10"
          >
            Download sample CSV
          </button>
        </div>
      </section>

      {/* Results */}
      {result && (
        <div className="mt-8 space-y-6">
          <section className="glass-panel p-5 sm:p-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Bank rows" value={String(result.stats.bank_rows)} />
              <Stat label="Matched" value={String(result.stats.matched)} accent="text-emerald-300" />
              <Stat label="Unmatched bank" value={String(result.stats.unmatched_bank)} accent="text-amber-300" />
              <Stat label="Match rate" value={`${result.stats.match_rate_pct}%`} accent="text-cyan-300" />
            </div>
          </section>

          {result.matched.length > 0 && (
            <section className="glass-panel p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-slate-50">Matched ({result.matched.length})</h2>
              <ul className="mt-4 space-y-2">
                {result.matched.map((m) => (
                  <li
                    key={m.bank_row}
                    className="flex items-center justify-between gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-100">
                        {m.bank_merchant || "(no merchant)"} <span className="text-xs text-slate-500">→ receipt #{m.receipt_id}</span>
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {m.bank_date.slice(0, 10)} · score {m.score.toFixed(2)}
                      </p>
                    </div>
                    <span className="shrink-0 font-mono tabular-nums text-emerald-300">
                      {formatCurrency(m.bank_amount, null)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {result.unmatched_bank.length > 0 && (
            <section className="glass-panel p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-amber-200">
                Bank charges with no receipt ({result.unmatched_bank.length})
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                These charges hit your bank but you haven&apos;t uploaded a receipt for them.
              </p>
              <ul className="mt-4 space-y-2">
                {result.unmatched_bank.map((u) => (
                  <li
                    key={u.row}
                    className="flex items-center justify-between gap-4 rounded-xl border border-amber-500/20 bg-amber-500/[0.04] px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-100">{u.merchant || "(no merchant)"}</p>
                      <p className="truncate text-xs text-slate-500">{u.date.slice(0, 10)} · row {u.row}</p>
                    </div>
                    <span className="shrink-0 font-mono tabular-nums text-amber-200">
                      {formatCurrency(u.amount, null)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {result.unmatched_receipts.length > 0 && (
            <section className="glass-panel p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-slate-200">
                Receipts not in your statement ({result.unmatched_receipts.length})
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                These receipts were uploaded but don&apos;t appear on the bank CSV. Likely paid in cash, or pre-dating the statement window.
              </p>
              <ul className="mt-4 space-y-2">
                {result.unmatched_receipts.slice(0, 20).map((u) => (
                  <li
                    key={u.receipt_id}
                    className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-100">{u.store_name ?? `Receipt #${u.receipt_id}`}</p>
                      <p className="truncate text-xs text-slate-500">{u.receipt_date.slice(0, 10)}</p>
                    </div>
                    <span className="shrink-0 font-mono tabular-nums text-slate-200">
                      {formatCurrency(u.total_amount, u.currency)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </main>
  );
}


function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 font-mono text-2xl font-semibold tabular-nums ${accent ?? "text-slate-100"}`}>
        {value}
      </p>
    </div>
  );
}
