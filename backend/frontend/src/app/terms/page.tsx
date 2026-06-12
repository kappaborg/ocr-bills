import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern your use of ExTaSy.",
};

const UPDATED = "June 14, 2026";

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">Legal</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">Terms of Service</h1>
      <p className="mt-2 text-sm text-slate-500">Last updated: {UPDATED}</p>

      <div className="mt-8 space-y-8 text-sm leading-relaxed text-slate-300">
        <section>
          <h2 className="text-lg font-semibold text-slate-100">The service</h2>
          <p className="mt-3">
            ExTaSy is an expense-tracking service that extracts data from receipt photos, organizes
            your spending, and offers price comparisons based on community data. By creating an
            account you agree to these terms.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Plans &amp; billing</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>The Free plan includes a monthly receipt quota at no cost, no card required.</li>
            <li>Paid plans renew monthly via Stripe and may start with a free trial. You can cancel anytime from Settings; access continues until the end of the paid period.</li>
            <li>Prices may change with at least 30 days&apos; notice.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Acceptable use</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>Upload only receipts you have the right to process.</li>
            <li>No attempts to pollute the community price feed with fabricated data, scrape the service, probe accounts that aren&apos;t yours, or circumvent rate limits and quotas.</li>
            <li>We may suspend accounts that abuse the service.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Price information</h2>
          <p className="mt-3">
            Price comparisons are derived from community-scanned receipts and are estimates, not
            offers. Actual store prices may differ. ExTaSy is not affiliated with the stores shown
            and earns nothing from your purchases (today).
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">OCR accuracy</h2>
          <p className="mt-3">
            Text extraction is automated and can make mistakes. You review and confirm every receipt
            before it counts — confirmed data is your responsibility. Do not rely on ExTaSy as a
            system of record for tax or legal purposes without verifying the data.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Warranty &amp; liability</h2>
          <p className="mt-3">
            The service is provided &quot;as is&quot; without warranties of any kind. To the maximum
            extent permitted by law, our total liability for any claim is limited to the amount you
            paid us in the 12 months preceding the claim.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Termination</h2>
          <p className="mt-3">
            You can delete your account at any time from Settings. We may terminate accounts that
            violate these terms. On deletion, your personal data is removed as described in the{" "}
            <Link href="/privacy" className="text-cyan-400 hover:underline">Privacy Policy</Link>.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Changes</h2>
          <p className="mt-3">
            We may update these terms; material changes will be announced in the app. Continued use
            after changes take effect constitutes acceptance.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-slate-100">Contact</h2>
          <p className="mt-3">
            <a href="mailto:kayrayilmazedu203@gmail.com" className="text-cyan-400 hover:underline">
              kayrayilmazedu203@gmail.com
            </a>
          </p>
        </section>
      </div>
    </main>
  );
}
