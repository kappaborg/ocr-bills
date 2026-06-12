"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import {
  addDueItemsToList,
  addShoppingItem,
  clearCheckedShoppingItems,
  deleteShoppingItem,
  getShoppingList,
  patchShoppingItem,
} from "@/lib/api";
import type { PriceOptionOut, ShoppingItemOut } from "@/lib/types";

/** Cheapest store for an item, or null when no price data exists yet. */
function bestOption(it: ShoppingItemOut): PriceOptionOut | null {
  return it.price_options?.[0] ?? null;
}

export default function ShoppingListPage() {
  const router = useRouter();
  const token = getAccessToken();
  const [items, setItems] = useState<ShoppingItemOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const reload = useCallback(() => {
    if (!token) return;
    getShoppingList(token)
      .then((res) => setItems(res.items ?? []))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load list"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    reload();
  }, [token, router, reload]);

  const addManual = async () => {
    const name = draft.trim();
    if (!name || !token) return;
    setBusy(true);
    try {
      await addShoppingItem(token, name);
      setDraft("");
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setBusy(false);
    }
  };

  const addDue = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const res = await addDueItemsToList(token);
      setItems(res.items ?? []);
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (it: ShoppingItemOut) => {
    if (!token) return;
    // Optimistic toggle — revert by reload on failure.
    setItems((prev) => prev.map((p) => (p.id === it.id ? { ...p, checked: !p.checked } : p)));
    try {
      await patchShoppingItem(token, it.id, { checked: !it.checked });
    } catch {
      reload();
    }
  };

  const remove = async (id: number) => {
    if (!token) return;
    setItems((prev) => prev.filter((p) => p.id !== id));
    try {
      await deleteShoppingItem(token, id);
    } catch {
      reload();
    }
  };

  const clearDone = async () => {
    if (!token) return;
    setBusy(true);
    try {
      await clearCheckedShoppingItems(token);
      reload();
    } finally {
      setBusy(false);
    }
  };

  // Group UNCHECKED items by their cheapest store; items without price data
  // fall into "Anywhere". Subtotals are per-currency within a store group.
  const grouped = useMemo(() => {
    const open = items.filter((i) => !i.checked);
    const m = new Map<string, { display: string; items: ShoppingItemOut[] }>();
    for (const it of open) {
      const best = bestOption(it);
      const key = best?.store ?? "__anywhere";
      const display = best?.store_display ?? "Anywhere";
      if (!m.has(key)) m.set(key, { display, items: [] });
      m.get(key)!.items.push(it);
    }
    return Array.from(m.entries()).map(([key, group]) => {
      const subtotals = new Map<string, number>();
      for (const it of group.items) {
        const best = bestOption(it);
        if (best) {
          subtotals.set(best.currency, (subtotals.get(best.currency) ?? 0) + best.price * it.quantity);
        }
      }
      return { key, ...group, subtotals: Array.from(subtotals.entries()) };
    });
  }, [items]);

  const done = items.filter((i) => i.checked);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">Plan</p>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">Shopping list</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={addDue}
            disabled={busy}
            className="rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10 disabled:opacity-50"
          >
            + Add due items
          </button>
          {done.length > 0 && (
            <button
              type="button"
              onClick={clearDone}
              disabled={busy}
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-400 hover:bg-white/10 disabled:opacity-50"
            >
              Clear {done.length} done
            </button>
          )}
        </div>
      </div>

      {/* Manual add */}
      <form
        className="mt-5 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          addManual();
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add an item — milk, coffee, batteries…"
          className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-950/70 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110 disabled:opacity-50"
        >
          Add
        </button>
      </form>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      {loading ? (
        <div className="mt-8 h-48 animate-pulse rounded-2xl bg-white/5" />
      ) : items.length === 0 ? (
        <div className="mt-12 text-center">
          <p className="text-slate-400">Your list is empty.</p>
          <p className="mt-2 text-sm text-slate-500">
            Add items above, or pull in everything that&apos;s due from{" "}
            <Link href="/need-to-buy" className="text-cyan-400 hover:underline">
              Need to buy
            </Link>
            .
          </p>
        </div>
      ) : (
        <div className="mt-8 space-y-5">
          {/* Store groups (open items) */}
          {grouped.map((group) => (
            <section key={group.key} className="glass-panel p-5">
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-sm font-semibold text-slate-100">
                  {group.key === "__anywhere" ? "Anywhere" : `At ${group.display}`}
                </h2>
                {group.subtotals.length > 0 && (
                  <p className="font-mono text-xs tabular-nums text-emerald-300">
                    ≈ {group.subtotals.map(([ccy, total]) => `${total.toFixed(2)} ${ccy}`).join(" + ")}
                  </p>
                )}
              </div>
              <ul className="mt-3 space-y-1.5">
                {group.items.map((it) => {
                  const best = bestOption(it);
                  return (
                    <li
                      key={it.id}
                      className="flex items-center gap-3 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2.5"
                    >
                      <input
                        type="checkbox"
                        checked={it.checked}
                        onChange={() => toggle(it)}
                        className="h-4 w-4 accent-emerald-500"
                        aria-label={`Mark ${it.product_name} as bought`}
                      />
                      <span className="min-w-0 flex-1 truncate text-sm text-slate-100">
                        {it.product_name}
                        {it.quantity !== 1 && (
                          <span className="ml-1.5 text-xs text-slate-500">×{it.quantity}</span>
                        )}
                      </span>
                      {best && (
                        <span className="shrink-0 font-mono text-xs tabular-nums text-slate-400">
                          {best.price.toFixed(2)} {best.currency}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => remove(it.id)}
                        className="shrink-0 text-slate-600 hover:text-red-400"
                        aria-label={`Remove ${it.product_name}`}
                      >
                        ✕
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}

          {/* Done */}
          {done.length > 0 && (
            <section className="glass-panel p-5 opacity-70">
              <h2 className="text-sm font-semibold text-slate-400">In the basket</h2>
              <ul className="mt-3 space-y-1.5">
                {done.map((it) => (
                  <li key={it.id} className="flex items-center gap-3 px-3 py-1.5">
                    <input
                      type="checkbox"
                      checked
                      onChange={() => toggle(it)}
                      className="h-4 w-4 accent-emerald-500"
                      aria-label={`Mark ${it.product_name} as not bought`}
                    />
                    <span className="flex-1 truncate text-sm text-slate-500 line-through">
                      {it.product_name}
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
