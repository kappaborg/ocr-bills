import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How ExTaSy collects, uses, and protects your data.",
};

const UPDATED = "June 14, 2026";

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">Legal</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">Privacy Policy</h1>
      <p className="mt-2 text-sm text-slate-500">Last updated: {UPDATED}</p>

      <div className="prose-invert mt-8 space-y-8 text-sm leading-relaxed text-slate-300">
        <section>
          <h2 className="text-lg font-semibold text-slate-100">What we collect</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li><strong>Account data</strong> — your email address and a hashed password. We never store passwords in plain text.</li>
            <li><strong>Receipt data</strong> — photos of receipts you upload and the structured data extracted from them (store, date, items, prices, currency).</li>
            <li><strong>Usage events</strong> — limited product events such as which price suggestion you tapped, used to improve recommendations.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">How your receipts are processed</h2>
          <p className="mt-3">
            Receipt images are processed with optical character recognition. Depending on server
            configuration this uses Google&apos;s Gemini API, which means the receipt image is
            transmitted to Google for text extraction under{" "}
            <a href="https://ai.google.dev/gemini-api/terms" className="text-cyan-400 hover:underline" target="_blank" rel="noopener noreferrer">
              Google&apos;s API terms
            </a>. Extracted data is stored in our database (hosted on Supabase, EU region).
            Original images are kept in temporary storage and may be removed on server restarts.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Anonymous price data</h2>
          <p className="mt-3">
            When you confirm a receipt, the prices on it (product, store, price, date) are added to
            an <strong>anonymous</strong> community price feed that powers price comparisons for all
            users. These price points are stored without your identity and cannot be traced back to
            you by other users. Deleting your account removes the link between you and these data
            points permanently.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Analytics &amp; cookies</h2>
          <p className="mt-3">
            The web app uses Vercel Analytics, which is cookieless and does not track you across
            sites. We use localStorage to keep you signed in and remember preferences (theme,
            display currency). We do not run advertising trackers.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Payments</h2>
          <p className="mt-3">
            Paid subscriptions are processed by Stripe. Your card details go directly to Stripe and
            never touch our servers. We store only your Stripe customer reference and subscription
            status.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Your rights</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li><strong>Export</strong> — download all your data as JSON from Settings at any time.</li>
            <li><strong>Delete</strong> — permanently delete your account and all associated data from Settings. This is immediate and irreversible.</li>
            <li><strong>Access &amp; correction</strong> — your receipts and items are fully editable in the app.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Data retention &amp; security</h2>
          <p className="mt-3">
            We keep your data for as long as your account exists. Connections are encrypted with
            TLS; passwords are hashed; session tokens expire after 24 hours. No system is perfectly
            secure — avoid uploading documents that contain information you wouldn&apos;t want
            processed (e.g., medical receipts with sensitive details).
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Contact</h2>
          <p className="mt-3">
            Questions or requests:{" "}
            <a href="mailto:kayrayilmazedu203@gmail.com" className="text-cyan-400 hover:underline">
              kayrayilmazedu203@gmail.com
            </a>
          </p>
        </section>
      </div>

      <p className="mt-12 text-xs text-slate-600">
        See also our <Link href="/terms" className="text-slate-400 hover:underline">Terms of Service</Link>.
      </p>
    </main>
  );
}
