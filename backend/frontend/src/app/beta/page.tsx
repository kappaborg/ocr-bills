import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Beta",
  description: "Install the ExTaSy Android beta and try it for two weeks.",
};

export default function BetaPage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">Beta · invite only</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">Welcome to the ExTaSy beta</h1>
      <p className="mt-3 text-slate-400">
        Thanks for trying this early. Your feedback in the next two weeks decides what we build next.
      </p>

      <section className="mt-10 space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">1 · Install on Android</h2>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-300">
          <li>
            <a href="/beta/extasy.apk" className="text-cyan-400 hover:underline" download>
              Download the APK
            </a>{" "}
            on your phone (55 MB).
          </li>
          <li>
            Open the file. Android may warn about installing from outside the Play Store — choose{" "}
            <strong>Install anyway</strong>. (You can revoke the permission after install.)
          </li>
          <li>Open the app and create an account with your real email — we&apos;ll use it to contact you about your feedback.</li>
        </ol>
        <p className="text-xs text-slate-500">
          iOS beta isn&apos;t available yet — Android only for now.
        </p>
      </section>

      <section className="mt-10 space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">2 · Try these five things</h2>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-300">
          <li>Scan three different receipts (camera or gallery). Bosnian, Serbian, English — try mixing languages.</li>
          <li>Confirm at least one and check the dashboard.</li>
          <li>Open the <strong>Inventory</strong> tab once you have a few confirmed receipts and check the price chips at the top.</li>
          <li>Open the <strong>Shopping list</strong> (cart icon in Inventory), tap <em>+ Add due items</em>, and add one item manually.</li>
          <li>Tap a price chip on the inventory page — it should open Google Maps directions to that store.</li>
        </ol>
      </section>

      <section className="mt-10 space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">3 · Tell us what happened</h2>
        <p className="text-sm text-slate-300">
          Every screen has a <strong>Send feedback</strong> tile in Settings — it opens your email
          with your device info prefilled. Be honest. The most useful answers:
        </p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-400">
          <li>What did you not understand?</li>
          <li>What did you expect to happen but didn&apos;t?</li>
          <li>Would you use this again next week?</li>
          <li>Would you pay $5/month for it?</li>
        </ul>
      </section>

      <section className="mt-10 space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">A note on privacy</h2>
        <p className="text-sm text-slate-400">
          The app records anonymous usage events and session replays during the beta so we can see
          what trips people up. Stop and start sessions normally — we don&apos;t see your password,
          and you can delete your data at any time from Settings. Full details in our{" "}
          <Link href="/privacy" className="text-cyan-400 hover:underline">Privacy Policy</Link>.
        </p>
      </section>

      <p className="mt-12 text-center text-xs text-slate-600">
        Questions:{" "}
        <a href="mailto:goldenkapparu@gmail.com" className="text-slate-400 hover:underline">
          goldenkapparu@gmail.com
        </a>
      </p>
    </main>
  );
}
