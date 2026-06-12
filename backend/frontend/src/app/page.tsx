import Image from "next/image";
import Link from "next/link";
import { BottomCta, HeaderAuthCta, HeroCtas } from "@/components/AuthCtas";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ocr-bills.vercel.app";

type PlanInfo = {
  id: string;
  name: string;
  price_cents: number;
  receipts_per_month: number | null;
  features: string[];
};

// Server-side plans fetch — revalidated hourly. Failure degrades to no
// pricing teaser rather than blocking the page.
async function fetchPlans(): Promise<PlanInfo[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/billing/plans`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.plans ?? []) as PlanInfo[];
  } catch {
    return [];
  }
}

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

// JSON-LD structured data — tells Google this is a SaaS product with a free
// tier. Helps rich results + knowledge panel eligibility.
function jsonLd(plans: PlanInfo[]) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "ExTaSy",
    applicationCategory: "FinanceApplication",
    operatingSystem: "Web, Android, iOS",
    url: SITE_URL,
    description:
      "Receipt OCR in any language with multi-currency expense tracking, budgets, recurring-expense detection, bank reconciliation, and accountant-ready exports.",
    offers: plans.map((p) => ({
      "@type": "Offer",
      name: p.name,
      price: (p.price_cents / 100).toFixed(2),
      priceCurrency: "USD",
    })),
  };
}

export default async function Landing() {
  const plans = await fetchPlans();

  return (
    <main className="relative isolate">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd(plans)) }}
      />

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
            <HeaderAuthCta />
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
          <HeroCtas />
        </div>
        <p className="mt-4 text-xs text-slate-500">
          Free forever for 20 receipts/month. No credit card required.
        </p>

        {/* Hero screenshot — real dashboard, browser-frame styled */}
        <div className="relative mx-auto mt-14 max-w-4xl">
          <div className="absolute -inset-6 rounded-3xl bg-gradient-to-r from-cyan-500/20 via-transparent to-emerald-500/20 blur-2xl" aria-hidden />
          <div className="relative overflow-hidden rounded-2xl border border-white/10 shadow-2xl shadow-cyan-500/10">
            <div className="flex items-center gap-1.5 border-b border-white/10 bg-slate-900/90 px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-green-500/70" />
              <span className="ml-3 select-none rounded-md bg-white/5 px-3 py-0.5 text-[10px] text-slate-500">
                ocr-bills.vercel.app/dashboard
              </span>
            </div>
            <Image
              src="/screenshots/dashboard.png"
              alt="ExTaSy dashboard showing spending totals, tax paid, and category breakdown"
              width={1440}
              height={900}
              priority
              className="w-full"
            />
          </div>
        </div>
      </section>

      {/* Receipt-review screenshot + copy split */}
      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">
              Smart review
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-50">
              Every line item, parsed and verified
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-slate-400">
              This is a real Bosnian café receipt — items in the local language,
              prices in convertible marks. ExTaSy extracted every line, matched
              the total, and flagged nothing because nothing needed flagging.
              When OCR <em>is</em> unsure, low-confidence lines get highlighted
              so you check exactly what needs checking and skip what doesn&apos;t.
            </p>
            <ul className="mt-6 space-y-2 text-sm text-slate-300">
              <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Confidence-aware review — high-confidence items collapse out of the way</li>
              <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Sum check: items + tax reconciled against the printed total</li>
              <li className="flex items-start gap-2"><span className="text-emerald-400">✓</span> Live status while OCR runs — no refresh-and-pray</li>
            </ul>
          </div>
          <div className="relative">
            <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-emerald-500/15 to-transparent blur-xl" aria-hidden />
            <Image
              src="/screenshots/receipt.png"
              alt="Receipt review screen showing parsed line items from a Bosnian café receipt"
              width={1440}
              height={900}
              className="relative w-full rounded-2xl border border-white/10 shadow-xl"
            />
          </div>
        </div>
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
            <Link
              href="/pricing"
              className="rounded-xl border border-white/15 bg-white/5 px-6 py-3 text-sm font-semibold text-slate-200 transition hover:bg-white/10"
            >
              See full pricing
            </Link>
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
          <BottomCta />
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
