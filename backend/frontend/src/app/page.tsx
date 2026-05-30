"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth";
import { listPlans, type PlanInfo } from "@/lib/api";


const FEATURES: { title: string; body: string; icon: string }[] = [
  {
    icon: "◈",
    title: "OCR that handles any receipt",
    body: "Latin, Cyrillic, Arabic, CJK, Devanagari. Plug-in engines (Tesseract → Gemini → Claude → Mindee) so you choose the accuracy/cost tradeoff that fits.",
  },
  {
    icon: "$",
    title: "Multi-currency with live FX",
    body: "Receipts arrive in BAM, EUR, USD, JPY, whatever. Pick your display currency once and the dashboard converts every total in real time.",
  },
  {
    icon: "≡",
    title: "Budgets + recurring detection",
    body: "Monthly limits per category with progress bars. We learn which products you buy on a cadence and forecast your monthly fixed costs.",
  },
  {
    icon: "↻",
    title: "Bank statement reconciliation",
    body: "Upload your bank CSV — we match every charge to its receipt within ±2 days and ±5% and flag what's missing on either side.",
  },
  {
    icon: "↗",
    title: "Accountant-ready exports",
    body: "QuickBooks bank-import CSV, Xero bank-statement CSV, a professional PDF report, or a plain spreadsheet. One click each.",
  },
  {
    icon: "⛁",
    title: "Households + sharing",
    body: "Pool receipts with a partner via a share link. Per-member roles, shared inventory, shared spending insights.",
  },
];


export default function Landing() {
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [plans, setPlans] = useState<PlanInfo[]>([]);

  useEffect(() => {
    setToken(getAccessToken());
    setMounted(true);
    listPlans().then((r) => setPlans(r.plans)).catch(() => {});
  }, []);

  const cta = (label: string, href: string, primary = false) => (
    <Link
      href={href}
      className={`rounded-xl px-6 py-3 text-sm font-semibold transition ${
        primary
          ? "bg-gradient-to-r from-cyan-500 to-emerald-500 text-slate-950 shadow-lg shadow-cyan-500/25 hover:brightness-110"
          : "border border-white/15 bg-white/5 text-slate-200 hover:bg-white/10"
      }`}
    >
      {label}
    </Link>
  );

  // Match SSR until token state resolves to avoid the auth-aware buttons jumping.
  const showAuthedCtas = mounted && token;

  return (
    <main className="relative isolate">
      {/* Header bar (minimal — only logo + sign-in/dashboard) */}
      <header className="sticky top-0 z-40 border-b border-white/5 bg-slate-950/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2" title="ExTaSy — Expense Tracking System">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-emerald-500 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/20">
              ◈
            </span>
            <span className="font-semibold tracking-tight text-slate-100">
              Ex<span className="text-cyan-400">TaSy</span>
            </span>
          </Link>
          <nav className="flex items-center gap-2 text-sm">
            <Link href="/pricing" className="rounded-full px-3 py-1.5 text-slate-300 hover:bg-white/5">
              Pricing
            </Link>
            {showAuthedCtas ? (
              <Link
                href="/dashboard"
                className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-1.5 font-semibold text-slate-950 shadow hover:brightness-110"
              >
                Open dashboard
              </Link>
            ) : (
              <Link href="/login" className="rounded-full px-3 py-1.5 text-slate-300 hover:bg-white/5">
                Sign in
              </Link>
            )}
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-5xl px-4 pt-16 pb-12 text-center sm:px-6 sm:pt-24 sm:pb-16">
        <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">
          Expense tracking, in any language
        </p>
        <h1 className="mt-4 text-5xl font-semibold tracking-tight text-slate-50 sm:text-6xl">
          Receipts you can{" "}
          <span className="bg-gradient-to-r from-cyan-300 to-emerald-400 bg-clip-text text-transparent">
            actually
          </span>{" "}
          read.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-400">
          Snap a photo, get a perfectly parsed receipt — in Bosnian, Russian, Arabic,
          German, Turkish, Japanese, anything. Budgets, recurring-expense detection,
          bank reconciliation, and accountant-ready exports built in.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {showAuthedCtas ? (
            <>
              {cta("Open dashboard", "/dashboard", true)}
              {cta("New scan", "/upload")}
            </>
          ) : (
            <>
              {cta("Try it free", "/register", true)}
              {cta("See pricing", "/pricing")}
            </>
          )}
        </div>
        <p className="mt-4 text-xs text-slate-500">
          Free forever for 20 receipts/month. No credit card required.
        </p>
      </section>

      {/* Feature grid */}
      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="text-center text-3xl font-semibold tracking-tight text-slate-50">
          Built for receipts that don&apos;t fit the template
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-slate-400">
          Thermal-paper, multi-currency, multi-script — the cases competitors fail on.
        </p>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <article
              key={f.title}
              className="group rounded-2xl border border-white/10 bg-white/[0.03] p-6 transition hover:border-cyan-500/30 hover:bg-white/[0.05]"
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 text-xl text-cyan-300 ring-1 ring-cyan-500/30">
                {f.icon}
              </span>
              <h3 className="mt-4 text-lg font-semibold text-slate-100">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Pricing teaser */}
      {plans.length > 0 && (
        <section className="mx-auto max-w-5xl px-4 py-14 sm:px-6">
          <h2 className="text-center text-3xl font-semibold tracking-tight text-slate-50">
            Pricing that respects your wallet
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {plans.map((p) => {
              const featured = p.id === "pro";
              const isFree = p.id === "free";
              return (
                <div
                  key={p.id}
                  className={`rounded-2xl border p-5 ${
                    featured
                      ? "border-cyan-500/40 bg-gradient-to-b from-cyan-500/10 to-transparent ring-1 ring-cyan-500/20"
                      : "border-white/10 bg-white/[0.03]"
                  }`}
                >
                  <p className="text-sm font-medium text-slate-300">{p.name}</p>
                  <p className="mt-2 font-mono text-3xl font-semibold tabular-nums text-slate-100">
                    ${(p.price_cents / 100).toFixed(2)}
                    <span className="text-sm font-normal text-slate-500">/mo</span>
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {p.receipts_per_month === null
                      ? "Unlimited receipts"
                      : `${p.receipts_per_month} receipts/month`}
                  </p>
                  <p className="mt-3 text-xs text-slate-400">{p.features[0]}</p>
                  {!isFree && (
                    <p className="mt-1 text-xs text-slate-500">+ {p.features.length - 1} more</p>
                  )}
                </div>
              );
            })}
          </div>
          <div className="mt-8 flex justify-center">
            {cta("See full pricing", "/pricing")}
          </div>
        </section>
      )}

      {/* Bottom CTA */}
      <section className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
          Stop typing receipts into spreadsheets.
        </h2>
        <p className="mt-3 text-sm text-slate-400">
          Sign up in 10 seconds. First 20 scans are on us.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          {showAuthedCtas
            ? cta("Open dashboard", "/dashboard", true)
            : cta("Try it free", "/register", true)}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 text-center text-xs text-slate-600">
        <p>
          ExTaSy — Expense Tracking System ·{" "}
          <Link href="/pricing" className="hover:text-slate-400">Pricing</Link>
          {" · "}
          <Link href="/login" className="hover:text-slate-400">Sign in</Link>
        </p>
      </footer>
    </main>
  );
}
