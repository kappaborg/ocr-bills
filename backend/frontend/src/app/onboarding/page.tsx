"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getAccessToken } from "@/lib/auth";
import { SUPPORTED_DISPLAY_CURRENCIES } from "@/lib/format";


const DISPLAY_CCY_KEY = "ocrbills:displayCurrency";
const TOTAL_STEPS = 3;


export default function OnboardingPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [step, setStep] = useState(0);

  // Step 1 — currency
  const [currency, setCurrency] = useState("BAM");

  useEffect(() => {
    setToken(getAccessToken());
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (!token) router.replace("/login");
  }, [mounted, token, router]);

  const finish = () => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(DISPLAY_CCY_KEY, currency);
      window.localStorage.setItem("ocrbills:onboarded", "1");
    }
    router.replace("/dashboard");
  };

  const next = () => {
    if (step + 1 >= TOTAL_STEPS) finish();
    else setStep(step + 1);
  };

  if (!mounted) {
    return (
      <main className="mx-auto max-w-xl px-4 py-12">
        <div className="h-72 animate-pulse rounded-2xl bg-white/5" />
      </main>
    );
  }
  if (!token) return null;

  return (
    <main className="mx-auto max-w-xl px-4 py-12 sm:px-6">
      {/* Stepper */}
      <div className="mb-8 flex items-center justify-center gap-2">
        {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
          <span
            key={i}
            className={`h-1.5 w-12 rounded-full transition ${
              i <= step ? "bg-cyan-400" : "bg-white/10"
            }`}
          />
        ))}
      </div>
      <p className="text-center text-xs uppercase tracking-[0.2em] text-cyan-400/90">
        Step {step + 1} of {TOTAL_STEPS}
      </p>

      <section className="mt-3 glass-panel p-6 sm:p-8">
        {step === 0 && (
          <StepCurrency currency={currency} setCurrency={setCurrency} />
        )}
        {step === 1 && <StepScan />}
        {step === 2 && <StepWrap currency={currency} />}

        <div className="mt-8 flex items-center justify-between">
          <button
            type="button"
            onClick={() => router.replace("/dashboard")}
            className="text-sm text-slate-500 hover:text-slate-300"
          >
            Skip for now
          </button>
          <div className="flex gap-2">
            {step > 0 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
              >
                Back
              </button>
            )}
            <button
              type="button"
              onClick={next}
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-5 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
            >
              {step + 1 === TOTAL_STEPS ? "Get started" : "Continue"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}


function StepCurrency({
  currency,
  setCurrency,
}: {
  currency: string;
  setCurrency: (c: string) => void;
}) {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
        Pick your display currency
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        Receipts can be in any currency — but the dashboard converts everything to one
        so totals make sense at a glance. You can change this later.
      </p>

      <div className="mt-6">
        <label className="block">
          <span className="text-xs uppercase tracking-wider text-slate-500">Show totals in</span>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="mt-2 w-full rounded-xl border border-white/15 bg-slate-950/80 px-4 py-3 text-sm font-medium text-slate-100 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
          >
            {SUPPORTED_DISPLAY_CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <p className="mt-3 text-xs text-slate-500">
          Rates refresh daily from frankfurter.app (ECB-derived).
        </p>
      </div>
    </>
  );
}


function StepScan() {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
        Two ways to add a receipt
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        Upload a photo or scan one with your camera. We&apos;ll OCR the text, extract
        line items, and ask you to confirm anything that looks off.
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <Link
          href="/upload"
          className="group rounded-xl border border-white/10 bg-slate-950/50 p-5 transition hover:border-cyan-400/40 hover:bg-cyan-500/[0.04]"
        >
          <p className="text-2xl">↑</p>
          <p className="mt-3 font-medium text-slate-100">Upload a photo</p>
          <p className="mt-1 text-xs text-slate-500">JPG or PNG up to 8 MB</p>
        </Link>
        <Link
          href="/scan"
          className="group rounded-xl border border-white/10 bg-slate-950/50 p-5 transition hover:border-cyan-400/40 hover:bg-cyan-500/[0.04]"
        >
          <p className="text-2xl">◉</p>
          <p className="mt-3 font-medium text-slate-100">Use your camera</p>
          <p className="mt-1 text-xs text-slate-500">Live receipt-frame overlay</p>
        </Link>
      </div>

      <p className="mt-4 text-xs text-slate-500">
        First 20 scans this month are on the free tier — no credit card required.
      </p>
    </>
  );
}


function StepWrap({ currency }: { currency: string }) {
  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
        You&apos;re ready
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        We&apos;ll show totals in <span className="font-medium text-cyan-300">{currency}</span>.
        Your free tier includes 20 receipts/month. When you need more, the dashboard
        will offer an upgrade.
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <Feature title="Need higher accuracy?" body="Plug in a Gemini API key (free tier 1500/day) — settings.OCR_ENGINE." />
        <Feature title="Have an accountant?" body="Pro unlocks QuickBooks and Xero CSV exports." />
        <Feature title="Travel often?" body="Receipts in any currency convert to your display currency live." />
        <Feature title="Shared expenses?" body="Business plan supports household sharing via invite links." />
      </div>
    </>
  );
}


function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4">
      <p className="text-sm font-medium text-slate-100">{title}</p>
      <p className="mt-1 text-xs text-slate-400">{body}</p>
    </div>
  );
}
