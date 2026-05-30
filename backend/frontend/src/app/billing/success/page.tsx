"use client";

import Link from "next/link";

export default function BillingSuccessPage() {
  return (
    <main className="mx-auto flex max-w-md flex-col items-center px-4 py-16 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20 text-3xl text-emerald-300 ring-1 ring-emerald-500/40">
        ✓
      </span>
      <h1 className="mt-4 text-2xl font-semibold text-slate-50">You&apos;re in</h1>
      <p className="mt-2 text-sm text-slate-400">
        Stripe is confirming your subscription. Your new plan will be active in a few seconds — refresh the dashboard if it hasn&apos;t switched yet.
      </p>
      <div className="mt-6 flex gap-3">
        <Link
          href="/dashboard"
          className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
        >
          Go to dashboard
        </Link>
        <Link href="/settings" className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 hover:bg-white/10">
          Manage billing
        </Link>
      </div>
    </main>
  );
}
