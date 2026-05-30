"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import { listInventory } from "@/lib/api";
import type { InventoryItemOut } from "@/lib/types";

function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
}

export default function InventoryPage() {
  const router = useRouter();
  const token = getAccessToken();
  const [items, setItems] = useState<InventoryItemOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    setLoading(true);
    setError(null);
    listInventory(token)
      .then((res) => setItems(res.results ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load inventory"))
      .finally(() => setLoading(false));
  }, [token, router]);

  const grouped = useMemo(() => {
    const m = new Map<string, InventoryItemOut[]>();
    for (const it of items) {
      const key = it.category_name ?? "Uncategorized";
      const arr = m.get(key) ?? [];
      arr.push(it);
      m.set(key, arr);
    }
    for (const arr of Array.from(m.values())) {
      arr.sort((a, b) => (b.purchase_count ?? 0) - (a.purchase_count ?? 0));
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [items]);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
        Inventory
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
        Your products
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        This view is built from confirmed receipts. It powers “need to buy”.
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
          <div className="glass-panel space-y-3 p-6">
            <div className="h-4 w-32 animate-pulse rounded-md bg-white/10" />
            <div className="h-16 animate-pulse rounded-xl bg-white/5" />
            <div className="h-16 animate-pulse rounded-xl bg-white/5" />
            <div className="h-16 animate-pulse rounded-xl bg-white/5" />
          </div>
        ) : items.length === 0 ? (
          <div className="glass-panel p-8 text-center">
            <p className="text-3xl">📦</p>
            <h2 className="mt-3 text-lg font-semibold text-slate-100">No products yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
              Inventory is built automatically from your confirmed receipts. The more receipts
              you confirm, the more accurate your &quot;need to buy&quot; predictions become.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <button
                type="button"
                onClick={() => router.push("/upload")}
                className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
              >
                Upload a receipt
              </button>
              <button
                type="button"
                onClick={() => router.push("/dashboard")}
                className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 hover:bg-white/10"
              >
                Back to dashboard
              </button>
            </div>
          </div>
        ) : (
          grouped.map(([cat, arr]) => (
            <section key={cat} className="glass-panel p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-slate-100">{cat}</h2>
                <p className="text-xs text-slate-500">{arr.length} items</p>
              </div>

              <div className="mt-4 overflow-hidden rounded-xl border border-white/10">
                <div className="grid grid-cols-[minmax(0,1fr)_110px_110px] gap-0 bg-slate-950/40 px-4 py-2 text-xs font-medium text-slate-400">
                  <span>Product</span>
                  <span className="text-right">Last</span>
                  <span className="text-right">Buys</span>
                </div>
                <div className="divide-y divide-white/10">
                  {arr.map((it) => (
                    <div
                      key={it.product_id}
                      className="grid grid-cols-[minmax(0,1fr)_110px_110px] items-center gap-0 bg-slate-950/70 px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-100">
                          {it.product_name}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          Next expected: {fmtDate(it.next_expected_buy_date)}
                        </p>
                      </div>
                      <p className="text-right text-xs font-mono text-slate-300">
                        {fmtDate(it.last_purchased_at)}
                      </p>
                      <p className="text-right text-xs font-mono text-cyan-300">
                        {it.purchase_count ?? 0}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          ))
        )}
      </div>
    </main>
  );
}

