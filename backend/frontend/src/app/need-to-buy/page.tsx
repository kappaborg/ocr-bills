"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import { listNeedToBuy } from "@/lib/api";
import type { NeedToBuyItemOut } from "@/lib/types";

function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
}

export default function NeedToBuyPage() {
  const router = useRouter();
  const token = getAccessToken();
  const [items, setItems] = useState<NeedToBuyItemOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    setLoading(true);
    setError(null);
    listNeedToBuy(token, 2)
      .then((res) => setItems(res.results ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load recommendations"))
      .finally(() => setLoading(false));
  }, [token, router]);

  const grouped = useMemo(() => {
    const m = new Map<string, NeedToBuyItemOut[]>();
    for (const it of items) {
      const key = it.category_name ?? "Uncategorized";
      const arr = m.get(key) ?? [];
      arr.push(it);
      m.set(key, arr);
    }
    for (const arr of Array.from(m.values())) {
      arr.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [items]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-10">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
        Need to buy
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
        Smart shopping list
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        Baseline AI: predicts what’s due soon based on your purchase intervals.
      </p>


      {error ? (
        <div
          role="alert"
          className="mt-6 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200"
        >
          {error}
        </div>
      ) : null}

      <div className="mt-8 space-y-6">
        {loading ? (
          <div className="glass-panel p-6 text-sm text-slate-400">Loading…</div>
        ) : items.length === 0 ? (
          <div className="glass-panel p-6 text-sm text-slate-400">
            Nothing is due yet. Confirm more receipts to improve predictions.
          </div>
        ) : (
          grouped.map(([cat, arr]) => (
            <section key={cat} className="glass-panel p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-slate-100">{cat}</h2>
                <p className="text-xs text-slate-500">{arr.length} items</p>
              </div>

              <div className="mt-4 space-y-2">
                {arr.map((it) => (
                  <div
                    key={it.product_id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-100">
                        {it.product_name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Last: {fmtDate(it.last_purchased_at)} · Expected:{" "}
                        {fmtDate(it.next_expected_buy_date)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs font-mono text-emerald-300">
                        score {it.score.toFixed(2)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))
        )}
      </div>
    </main>
  );
}

