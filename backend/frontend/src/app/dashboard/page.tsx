"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import {
  deleteReceipt,
  exportTransactionsCsv,
  exportTransactionsPdf,
  getFxRates,
  getMyBilling,
  listBudgets,
  listInsights,
  listReceipts,
  listRecurring,
  listTransactions,
  searchReceipts,
  upsertBudget,
  type BillingMe,
  type BudgetOut,
  type RecurringItem,
} from "@/lib/api";
import { InsightOut, ReceiptOut, TransactionOut } from "@/lib/types";
import {
  SUPPORTED_DISPLAY_CURRENCIES,
  convertCurrency,
  formatCurrency,
  setFxRates,
} from "@/lib/format";

const DISPLAY_CCY_KEY = "ocrbills:displayCurrency";
const DATE_RANGE_KEY = "ocrbills:dateRange";

type DateRange = "7d" | "30d" | "365d" | "all";
const DATE_RANGE_OPTS: { value: DateRange; label: string; days: number | null }[] = [
  { value: "7d", label: "Week", days: 7 },
  { value: "30d", label: "Month", days: 30 },
  { value: "365d", label: "Year", days: 365 },
  { value: "all", label: "All time", days: null },
];

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-white/5 ${className}`} />;
}

export default function DashboardPage() {
  const router = useRouter();
  // Defer token read until after mount — getAccessToken() touches localStorage,
  // which is unavailable during SSR. Returning a stable skeleton until mount
  // keeps server and first client render identical (avoids hydration mismatch).
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setToken(getAccessToken());
    setMounted(true);
  }, []);

  const [transactions, setTransactions] = useState<TransactionOut[]>([]);
  const [insights, setInsights] = useState<InsightOut[]>([]);
  const [budgets, setBudgets] = useState<BudgetOut[]>([]);
  const [recurring, setRecurring] = useState<RecurringItem[]>([]);
  const [recurringForecast, setRecurringForecast] = useState(0);
  const [receipts, setReceipts] = useState<ReceiptOut[]>([]);
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [searchResults, setSearchResults] = useState<ReceiptOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [exportLoading, setExportLoading] = useState<null | "csv" | "csv-qb" | "csv-xero" | "pdf">(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // ── Settings: display currency + date range, both localStorage-backed
  const [displayCurrency, setDisplayCurrency] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<DateRange>("30d");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const ccy = window.localStorage.getItem(DISPLAY_CCY_KEY);
    if (ccy) setDisplayCurrency(ccy);
    const dr = window.localStorage.getItem(DATE_RANGE_KEY) as DateRange | null;
    if (dr) setDateRange(dr);
  }, []);
  useEffect(() => {
    if (displayCurrency && typeof window !== "undefined")
      window.localStorage.setItem(DISPLAY_CCY_KEY, displayCurrency);
  }, [displayCurrency]);
  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(DATE_RANGE_KEY, dateRange);
  }, [dateRange]);

  // ── Initial data fetch (parallel) ──
  useEffect(() => {
    if (!mounted) return;            // wait for first client effect to read token
    if (!token) {
      router.replace("/login");
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([
      listTransactions(token),
      listInsights(token),
      listBudgets(token).catch(() => ({ results: [] })),   // pro+ only
      listRecurring(token, displayCurrency ?? "BAM").catch(() => ({ results: [], forecast_monthly_total: 0, currency: "BAM" })),
      listReceipts(token),
      getFxRates().catch(() => null),
      getMyBilling(token).catch(() => null),
    ])
      .then(([tx, ins, bud, rec, rec_full, fx, bill]) => {
        setTransactions(tx.results);
        setInsights(ins.results);
        setBudgets(bud.results);
        setRecurring(rec.results);
        setRecurringForecast(rec.forecast_monthly_total);
        setReceipts(rec_full);
        setBilling(bill);
        if (fx) setFxRates(fx.rates);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, router, mounted]);

  // Refresh recurring when display currency changes (server-side conversion).
  useEffect(() => {
    if (!token || !displayCurrency) return;
    listRecurring(token, displayCurrency)
      .then((rec) => {
        setRecurring(rec.results);
        setRecurringForecast(rec.forecast_monthly_total);
      })
      .catch(() => {});
  }, [displayCurrency, token]);

  const primaryCurrency = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of transactions) if (t.currency) counts.set(t.currency, (counts.get(t.currency) ?? 0) + 1);
    if (counts.size === 0) return null;
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1])[0][0];
  }, [transactions]);
  const effectiveDisplayCurrency = displayCurrency ?? primaryCurrency ?? "BAM";

  // ── Debounced API search (falls back to in-memory list when query empty) ──
  useEffect(() => {
    if (!token) return;
    const q = search.trim();
    if (!q) {
      setSearchResults(null);
      return;
    }
    const handle = setTimeout(() => {
      searchReceipts(token, q)
        .then((r) => setSearchResults(r.results))
        .catch(() => setSearchResults([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [search, token]);

  // ── Date range filtering ──
  const rangeCutoff = useMemo(() => {
    const days = DATE_RANGE_OPTS.find((o) => o.value === dateRange)?.days;
    if (days == null) return null;
    return new Date(Date.now() - days * 86_400_000);
  }, [dateRange]);

  const inRange = (iso: string | null | undefined) => {
    if (!rangeCutoff || !iso) return true;
    const d = new Date(iso);
    return !Number.isNaN(d.getTime()) && d >= rangeCutoff;
  };

  const rangedTransactions = useMemo(
    () => transactions.filter((t) => inRange(t.date)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [transactions, rangeCutoff],
  );

  const convert = (amount: number, fromCcy: string | null | undefined) =>
    convertCurrency(amount, fromCcy, effectiveDisplayCurrency) ?? amount;

  const totalsByCategory = useMemo(() => {
    const map = new Map<string, number>();
    for (const t of rangedTransactions) {
      const key = t.category_name ?? "Uncategorized";
      map.set(key, (map.get(key) ?? 0) + convert(t.item_price, t.currency));
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangedTransactions, effectiveDisplayCurrency]);

  const grandTotal = useMemo(
    () => rangedTransactions.reduce((s, t) => s + convert(t.item_price, t.currency), 0),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rangedTransactions, effectiveDisplayCurrency],
  );

  // Tax paid in the current date range — receipts have tax_amount in their
  // native currency, so we sum tax per receipt that falls in the window.
  const taxPaid = useMemo(() => {
    let total = 0;
    for (const r of receipts) {
      if (!r.tax_amount) continue;
      if (!inRange(r.receipt_date)) continue;
      total += convert(r.tax_amount, r.currency);
    }
    return total;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [receipts, effectiveDisplayCurrency, rangeCutoff]);

  const spendingSpike = useMemo(
    () => insights.find((i) => i.type === "spending_spike") ?? null,
    [insights],
  );

  const handleDeleteReceipt = async (receiptId: number) => {
    if (!token) return;
    if (!window.confirm("Delete this receipt and all its items? This cannot be undone.")) return;
    setDeletingId(receiptId);
    try {
      await deleteReceipt(receiptId, token);
      setTransactions((prev) => prev.filter((t) => t.receipt_id !== receiptId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };

  const handleExport = async (kind: "csv" | "csv-qb" | "csv-xero" | "pdf") => {
    if (!token) return;
    setExportLoading(kind);
    setExportMenuOpen(false);
    try {
      if (kind === "csv") await exportTransactionsCsv(token, "generic");
      else if (kind === "csv-qb") await exportTransactionsCsv(token, "quickbooks");
      else if (kind === "csv-xero") await exportTransactionsCsv(token, "xero");
      else await exportTransactionsPdf(token, { displayCurrency: effectiveDisplayCurrency });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportLoading(null);
    }
  };

  const handleSetBudget = async (categoryName: string, categoryId: number | null) => {
    if (!token) return;
    const input = window.prompt(
      `Monthly budget for ${categoryName} (${effectiveDisplayCurrency}):`,
      "100",
    );
    if (!input) return;
    const limit = parseFloat(input.replace(",", "."));
    if (!Number.isFinite(limit) || limit <= 0) return;
    try {
      const created = await upsertBudget(
        { category_id: categoryId, monthly_limit: limit, currency: effectiveDisplayCurrency },
        token,
      );
      setBudgets((prev) => {
        const others = prev.filter((b) => b.category_id !== categoryId);
        return [...others, created];
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save budget");
    }
  };

  // Derive receipt list from transactions for delete buttons
  const receiptIds = useMemo(() => {
    const seen = new Set<number>();
    const list: { receipt_id: number; store_name?: string | null }[] = [];
    for (const t of transactions) {
      if (!seen.has(t.receipt_id)) {
        seen.add(t.receipt_id);
        list.push({ receipt_id: t.receipt_id, store_name: t.store_name });
      }
    }
    return list;
  }, [transactions]);

  // Render a stable shell on the server and during the very first client
  // render. Once `mounted` flips true we know token state is consistent and
  // we render the real content (or redirect to /login if no token).
  if (!mounted) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-24" />
          <Skeleton className="h-40" />
          <Skeleton className="h-64" />
        </div>
      </main>
    );
  }
  if (!token) return null;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">Overview</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">Spending pulse</h1>
          <p className="mt-1 text-sm text-slate-400">Confirmed receipts → transactions → insights</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => router.push("/upload")}
            className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
          >
            New scan
          </button>
          <div className="relative">
            <button
              type="button"
              disabled={!!exportLoading || transactions.length === 0}
              onClick={() => setExportMenuOpen((v) => !v)}
              className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/10 disabled:opacity-40"
            >
              {exportLoading
                ? exportLoading === "pdf" ? "Generating…" : "Exporting…"
                : "Export ▾"}
            </button>
            {exportMenuOpen && (
              <div
                className="absolute right-0 z-20 mt-1 w-56 overflow-hidden rounded-xl border border-white/10 bg-slate-950/95 shadow-xl backdrop-blur"
                onMouseLeave={() => setExportMenuOpen(false)}
              >
                <ExportMenuItem
                  label="CSV (generic)"
                  hint="Plain spreadsheet"
                  onClick={() => handleExport("csv")}
                />
                <ExportMenuItem
                  label="QuickBooks CSV"
                  hint="Bank-import format"
                  premium={billing?.plan === "free"}
                  onClick={() => handleExport("csv-qb")}
                />
                <ExportMenuItem
                  label="Xero CSV"
                  hint="Bank-statement format"
                  premium={billing?.plan === "free"}
                  onClick={() => handleExport("csv-xero")}
                />
                <ExportMenuItem
                  label="PDF expense report"
                  hint={`Display currency: ${effectiveDisplayCurrency}`}
                  premium={billing?.plan === "free"}
                  onClick={() => handleExport("pdf")}
                />
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              clearAccessToken();
              router.replace("/login");
            }}
            className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
          >
            Log out
          </button>
        </div>
      </div>

      {/* Plan + quota bar */}
      {billing && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
          <div className="flex items-center gap-3">
            <span
              className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${
                billing.plan === "free"
                  ? "bg-slate-700/60 text-slate-300"
                  : billing.plan === "pro"
                    ? "bg-cyan-500/20 text-cyan-200 ring-1 ring-cyan-500/40"
                    : "bg-emerald-500/20 text-emerald-200 ring-1 ring-emerald-500/40"
              }`}
            >
              {billing.plan}
            </span>
            {billing.usage.receipts_quota === 0 ? (
              <span className="text-xs text-slate-400">Unlimited receipts</span>
            ) : (
              <span className="text-xs text-slate-400">
                {billing.usage.receipts_used} / {billing.usage.receipts_quota} receipts this month
              </span>
            )}
          </div>
          {billing.plan === "free" ? (
            <button
              type="button"
              onClick={() => router.push("/pricing")}
              className="rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 px-3 py-1 text-xs font-semibold text-slate-950 hover:brightness-110"
            >
              Upgrade
            </button>
          ) : null}
        </div>
      )}
      {billing && billing.usage.receipts_quota > 0 && (
        <div className="mb-6 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
          <div
            className={`h-full transition-all ${
              billing.usage.percent >= 100
                ? "bg-red-500"
                : billing.usage.percent >= 80
                  ? "bg-amber-400"
                  : "bg-cyan-400"
            }`}
            style={{ width: `${Math.min(100, billing.usage.percent)}%` }}
          />
        </div>
      )}

      {/* Date range chips */}
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <span className="text-xs uppercase tracking-wider text-slate-500">Range:</span>
        {DATE_RANGE_OPTS.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => setDateRange(o.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              dateRange === o.value
                ? "bg-cyan-500/20 text-cyan-200 ring-1 ring-cyan-500/40"
                : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {error ? (
        <div role="alert" className="mb-6 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-40" />
          <Skeleton className="h-32" />
          <Skeleton className="h-64" />
        </div>
      ) : (
        <div className="space-y-8">
          {/* Total spend + tax + currency selector + spike indicator */}
          {grandTotal > 0 && (
            <section className="glass-panel grid gap-4 p-5 sm:grid-cols-3 sm:p-6">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
                  Total spend ({DATE_RANGE_OPTS.find((o) => o.value === dateRange)?.label.toLowerCase()})
                </p>
                <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-cyan-300">
                  {formatCurrency(grandTotal, effectiveDisplayCurrency)}
                </p>
                {spendingSpike ? (
                  <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-red-500/20 px-2.5 py-0.5 text-[11px] font-semibold text-red-300 ring-1 ring-red-500/30">
                    ↑ {spendingSpike.message.match(/\+(\d+)%/)?.[1] ?? ""}% vs last week
                  </span>
                ) : (
                  <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
                    ✓ On track
                  </span>
                )}
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Tax paid (VAT / PDV)</p>
                <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-amber-300">
                  {formatCurrency(taxPaid, effectiveDisplayCurrency)}
                </p>
                <p className="mt-2 text-[11px] text-slate-500">
                  Parsed from {receipts.filter((r) => r.tax_amount && inRange(r.receipt_date)).length} receipts
                </p>
              </div>
              <div className="flex flex-col items-start gap-2 sm:items-end">
                <label htmlFor="display-ccy" className="text-xs uppercase tracking-wider text-slate-500">
                  Show in
                </label>
                <select
                  id="display-ccy"
                  value={effectiveDisplayCurrency}
                  onChange={(e) => setDisplayCurrency(e.target.value || null)}
                  className="rounded-xl border border-white/15 bg-slate-900/80 px-3 py-1.5 text-sm font-medium text-slate-100 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
                >
                  {SUPPORTED_DISPLAY_CURRENCIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </section>
          )}

          {/* Budgets — one bar per category with a configured limit */}
          {budgets.length > 0 && (
            <section className="glass-panel p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-slate-50">Monthly budgets</h2>
              <p className="mt-1 text-xs text-slate-500">
                Progress this month, projected end-of-month spend in brackets.
              </p>
              <ul className="mt-4 space-y-3">
                {budgets.map((b) => {
                  const pct = Math.min(150, b.percent);
                  const barColor = b.over_budget
                    ? "bg-red-500"
                    : b.percent > 80
                      ? "bg-amber-400"
                      : "bg-emerald-400";
                  return (
                    <li key={b.id} className="rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-slate-200">
                          {b.category_name ?? "Overall"}
                        </span>
                        <span className="font-mono text-xs tabular-nums text-slate-400">
                          {formatCurrency(b.spent, b.currency)} / {formatCurrency(b.monthly_limit, b.currency)}
                          <span className="ml-2 text-slate-500">
                            ({formatCurrency(b.projected_month_end, b.currency)})
                          </span>
                        </span>
                      </div>
                      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10">
                        <div className={`h-full ${barColor}`} style={{ width: `${Math.min(100, pct)}%` }} />
                      </div>
                      {b.over_budget && (
                        <p className="mt-1 text-xs text-red-300">
                          {b.percent.toFixed(0)}% — over budget by {formatCurrency(Math.abs(b.remaining), b.currency)}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {/* By category */}
          <section className="glass-panel p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-slate-50">By category</h2>
            {totalsByCategory.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">No confirmed spending in this range yet.</p>
            ) : (
              <ul className="mt-4 space-y-2">
                {totalsByCategory.map(([name, total]) => {
                  const budget = budgets.find((b) => b.category_name === name);
                  return (
                    <li
                      key={name}
                      className="group flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3"
                    >
                      <span className="font-medium text-slate-200">{name}</span>
                      <div className="flex items-center gap-3">
                        <span className="font-mono tabular-nums text-slate-100">
                          {formatCurrency(total, effectiveDisplayCurrency)}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            const id = budget?.category_id
                              ?? transactions.find((t) => t.category_name === name)?.category_id
                              ?? null;
                            handleSetBudget(name, id);
                          }}
                          className="invisible rounded-md px-2 py-1 text-xs text-slate-400 hover:bg-white/10 hover:text-slate-200 group-hover:visible"
                          title={budget ? "Edit budget" : "Set monthly budget"}
                        >
                          {budget ? "Edit" : "Budget"}
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* Insights */}
          <section className="glass-panel p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-slate-50">Insights</h2>
            {insights.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">No insights yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {insights.map((ins) => (
                  <li key={ins.id} className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
                    <p className="text-xs uppercase tracking-wider text-slate-500">{ins.type.replaceAll("_", " ")}</p>
                    <p className="mt-1 text-sm text-slate-200">{ins.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Recurring expenses */}
          {recurring.length > 0 && (
            <section className="glass-panel p-5 sm:p-6">
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-lg font-semibold text-slate-50">Recurring expenses</h2>
                <span className="font-mono text-sm tabular-nums text-cyan-300">
                  ≈ {formatCurrency(recurringForecast, effectiveDisplayCurrency)} / month
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Products you've bought repeatedly at a steady pace.
              </p>
              <ul className="mt-4 space-y-2">
                {recurring.slice(0, 6).map((r) => (
                  <li key={r.product_id} className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-100">{r.product_name}</p>
                      <p className="truncate text-xs text-slate-500">
                        {r.category_name ?? "Uncategorized"} · every ~{r.avg_interval_days}d · {r.purchase_count}× total
                      </p>
                    </div>
                    <span className="shrink-0 font-mono text-sm tabular-nums text-emerald-300">
                      {formatCurrency(r.projected_monthly_spend, r.currency)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Transactions — with API-backed search */}
          <section className="glass-panel p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-50">Transactions</h2>
              {transactions.length > 0 && (
                <div className="relative">
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search items, stores, raw text…"
                    className="w-64 rounded-xl border border-white/10 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
                  />
                  {search && (
                    <button
                      type="button"
                      onClick={() => setSearch("")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    >
                      ×
                    </button>
                  )}
                </div>
              )}
            </div>

            {searchResults !== null ? (
              <>
                <p className="mt-2 text-xs text-slate-500">
                  {searchResults.length} receipt{searchResults.length === 1 ? "" : "s"} match &quot;{search}&quot;
                </p>
                {searchResults.length === 0 ? (
                  <p className="mt-4 text-sm text-slate-500">No matches.</p>
                ) : (
                  <ul className="mt-4 space-y-2">
                    {searchResults.map((r) => (
                      <li
                        key={r.id}
                        className="cursor-pointer rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3 hover:border-cyan-500/40"
                        onClick={() => router.push(`/receipt/${r.id}`)}
                      >
                        <div className="flex items-center justify-between gap-4">
                          <div className="min-w-0">
                            <p className="truncate font-medium text-slate-100">{r.store_name ?? `Receipt #${r.id}`}</p>
                            <p className="text-xs text-slate-500">
                              {r.items.length} item{r.items.length === 1 ? "" : "s"} ·{" "}
                              {r.receipt_date ? new Date(r.receipt_date).toLocaleDateString() : "—"}
                            </p>
                          </div>
                          <span className="font-mono text-sm tabular-nums text-emerald-300">
                            {formatCurrency(r.total_amount ?? 0, r.currency)}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            ) : transactions.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">Confirm a receipt to see line items here.</p>
            ) : (
              <ul className="mt-4 space-y-2">
                {rangedTransactions.slice(0, 100).map((t) => {
                  const converted = convertCurrency(t.item_price, t.currency, effectiveDisplayCurrency);
                  const tooltip =
                    t.currency && t.currency !== effectiveDisplayCurrency && converted != null
                      ? `${formatCurrency(converted, effectiveDisplayCurrency)} in ${effectiveDisplayCurrency}`
                      : undefined;
                  return (
                    <li
                      key={`${t.receipt_id}-${t.id}`}
                      className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-100">{t.item_name}</p>
                        <p className="truncate text-xs text-slate-500">
                          {t.category_name ?? "Uncategorized"}
                          {t.store_name ? ` · ${t.store_name}` : ""}
                        </p>
                      </div>
                      <span
                        className="shrink-0 font-mono tabular-nums text-emerald-300"
                        title={tooltip}
                      >
                        {formatCurrency(t.item_price, t.currency)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* Receipts list with delete */}
          {receiptIds.length > 0 && (
            <section className="glass-panel p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-slate-50">Receipts</h2>
              <ul className="mt-4 space-y-2">
                {receiptIds.map(({ receipt_id, store_name }) => (
                  <li
                    key={receipt_id}
                    className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-100">
                        {store_name ?? `Receipt #${receipt_id}`}
                      </p>
                      <p className="text-xs text-slate-500">#{receipt_id}</p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => router.push(`/receipt/${receipt_id}`)}
                        className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-400 hover:bg-white/10 hover:text-slate-200 transition"
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        disabled={deletingId === receipt_id}
                        onClick={() => handleDeleteReceipt(receipt_id)}
                        className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-red-900/40 hover:text-red-300 disabled:opacity-50 transition"
                      >
                        {deletingId === receipt_id ? "Deleting…" : "Delete"}
                      </button>
                    </div>
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


function ExportMenuItem({
  label,
  hint,
  premium = false,
  onClick,
}: {
  label: string;
  hint: string;
  premium?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left text-sm text-slate-200 hover:bg-white/5"
    >
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-xs text-slate-500">{hint}</span>
      </span>
      {premium && (
        <span className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-cyan-200">
          Pro
        </span>
      )}
    </button>
  );
}
