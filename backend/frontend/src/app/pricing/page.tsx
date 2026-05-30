"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import { listPlans, startCheckout, type PlanInfo } from "@/lib/api";

export default function PricingPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [currency, setCurrency] = useState("USD");
  const [configured, setConfigured] = useState(true);
  const [trialDays, setTrialDays] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutFor, setCheckoutFor] = useState<string | null>(null);

  useEffect(() => {
    listPlans()
      .then((r) => {
        setPlans(r.plans);
        setCurrency(r.currency);
        setConfigured(r.configured);
        setTrialDays(r.trial_days ?? 0);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load pricing"))
      .finally(() => setLoading(false));
  }, []);

  const handleSubscribe = async (planId: "pro" | "business") => {
    const token = getAccessToken();
    if (!token) {
      router.push("/register?next=/pricing");
      return;
    }
    setCheckoutFor(planId);
    try {
      const r = await startCheckout(planId, token);
      window.location.href = r.checkout_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start checkout");
      setCheckoutFor(null);
    }
  };

  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="text-center">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">Pricing</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-50 sm:text-5xl">
          Simple, predictable plans
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-400">
          Free forever for casual use. Upgrade for higher limits, deeper insights, and team features.
        </p>
      </div>

      {error && (
        <p role="alert" className="mx-auto mt-6 max-w-xl rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-center text-sm text-red-200">
          {error}
        </p>
      )}

      {!configured && (
        <p className="mx-auto mt-6 max-w-2xl rounded-xl border border-amber-500/30 bg-amber-950/30 px-4 py-3 text-center text-xs text-amber-200">
          Billing is in setup mode — checkout flows are disabled until Stripe keys are configured. You can preview the plan structure below.
        </p>
      )}

      {loading ? (
        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-96 animate-pulse rounded-2xl bg-white/5" />
          ))}
        </div>
      ) : (
        <div className="mt-10 grid gap-5 sm:grid-cols-3">
          {plans.map((p) => {
            const featured = p.id === "pro";
            const isFree = p.id === "free";
            return (
              <section
                key={p.id}
                className={`relative flex flex-col rounded-2xl border p-6 ${
                  featured
                    ? "border-cyan-500/40 bg-gradient-to-b from-cyan-500/10 to-transparent ring-1 ring-cyan-500/20"
                    : "border-white/10 bg-white/[0.03]"
                }`}
              >
                {featured && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-cyan-500 px-3 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-950">
                    Most popular
                  </span>
                )}

                <header>
                  <h2 className="text-xl font-semibold text-slate-50">{p.name}</h2>
                  <div className="mt-3 flex items-baseline gap-1">
                    <span className="font-mono text-4xl font-semibold tabular-nums text-slate-100">
                      ${(p.price_cents / 100).toFixed(2)}
                    </span>
                    <span className="text-sm text-slate-500">/mo</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {p.receipts_per_month === null
                      ? "Unlimited receipts"
                      : `${p.receipts_per_month} receipts / month`}
                  </p>
                </header>

                <ul className="mt-6 flex-1 space-y-2">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-slate-300">
                      <span className="mt-0.5 text-cyan-400">✓</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  disabled={isFree || !configured || checkoutFor === p.id}
                  onClick={() => handleSubscribe(p.id as "pro" | "business")}
                  className={`mt-6 w-full rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                    isFree
                      ? "cursor-default border border-white/10 bg-white/5 text-slate-400"
                      : featured
                        ? "bg-gradient-to-r from-cyan-500 to-emerald-500 text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110 disabled:opacity-50"
                        : "border border-cyan-400/40 bg-slate-950 text-cyan-200 hover:bg-cyan-950/40 disabled:opacity-50"
                  }`}
                >
                  {isFree
                    ? "Current free tier"
                    : checkoutFor === p.id
                      ? "Redirecting…"
                      : configured
                        ? (trialDays > 0
                            ? `Start ${trialDays}-day free trial`
                            : `Subscribe to ${p.name}`)
                        : "Setup pending"}
                </button>
                {!isFree && configured && trialDays > 0 && (
                  <p className="mt-2 text-center text-[11px] text-slate-500">
                    No charge for {trialDays} days · cancel any time
                  </p>
                )}
              </section>
            );
          })}
        </div>
      )}

      <p className="mt-10 text-center text-xs text-slate-500">
        Prices in {currency}. Cancel anytime from your billing portal.
      </p>
    </main>
  );
}
