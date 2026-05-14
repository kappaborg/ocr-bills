"use client";

import { useEffect, useMemo, useState } from "react";
import { clearAccessToken, getAccessToken } from "@/lib/auth";
import { listInsights, listTransactions } from "@/lib/api";
import { InsightOut, TransactionOut } from "@/lib/types";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();
  const token = getAccessToken();

  const [transactions, setTransactions] = useState<TransactionOut[]>([]);
  const [insights, setInsights] = useState<InsightOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }

    setLoading(true);
    setError(null);
    Promise.all([listTransactions(token), listInsights(token)])
      .then(([t, i]) => {
        setTransactions(t.results);
        setInsights(i.results);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => setLoading(false));
  }, [token, router]);

  const totalsByCategory = useMemo(() => {
    const map = new Map<string, number>();
    for (const t of transactions) {
      const key = t.category_name ?? "Uncategorized";
      map.set(key, (map.get(key) ?? 0) + t.item_price);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [transactions]);

  if (!token) return null;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
            Overview
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
            Spending pulse
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Confirmed receipts → transactions → insights
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => router.push("/upload")}
            className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
          >
            New scan
          </button>
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

      {error ? (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200"
        >
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="glass-panel flex flex-col items-center justify-center gap-3 px-8 py-16">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
          <p className="text-sm text-slate-400">Loading your data…</p>
        </div>
      ) : (
        <div className="space-y-8">
          <section className="glass-panel p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-slate-50">By category</h2>
            {totalsByCategory.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">
                No confirmed spending yet. Scan a receipt to get started.
              </p>
            ) : (
              <ul className="mt-4 space-y-2">
                {totalsByCategory.map(([name, total]) => (
                  <li
                    key={name}
                    className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3"
                  >
                    <span className="font-medium text-slate-200">{name}</span>
                    <span className="font-mono tabular-nums text-slate-100">
                      {total.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="glass-panel p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-slate-50">Insights</h2>
            {insights.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">No insights yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {insights.map((ins) => (
                  <li
                    key={ins.id}
                    className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3"
                  >
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                      {ins.type.replaceAll("_", " ")}
                    </p>
                    <p className="mt-1 text-sm text-slate-200">{ins.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="glass-panel p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-slate-50">Transactions</h2>
            {transactions.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">
                Confirm a receipt to see line items here.
              </p>
            ) : (
              <ul className="mt-4 space-y-2">
                {transactions.slice(0, 100).map((t) => (
                  <li
                    key={`${t.receipt_id}-${t.id}`}
                    className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/50 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-100">
                        {t.item_name}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {t.category_name ?? "Uncategorized"}
                        {t.store_name ? ` · ${t.store_name}` : ""}
                      </p>
                    </div>
                    <span className="shrink-0 font-mono tabular-nums text-emerald-300">
                      {t.item_price.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
