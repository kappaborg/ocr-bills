"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function UnsubscribeInner() {
  const params = useSearchParams();
  const userId = params.get("u");
  const token = params.get("t");
  const [state, setState] = useState<"loading" | "confirm" | "done" | "already" | "invalid">("loading");
  const [email, setEmail] = useState<string>("");

  useEffect(() => {
    if (!userId || !token) {
      setState("invalid");
      return;
    }
    fetch(`${API_BASE}/admin/unsubscribe-status/${userId}?t=${encodeURIComponent(token)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: { email: string; unsubscribed: boolean }) => {
        setEmail(d.email);
        setState(d.unsubscribed ? "already" : "confirm");
      })
      .catch(() => setState("invalid"));
  }, [userId, token]);

  const doUnsubscribe = async () => {
    if (!userId || !token) return;
    setState("loading");
    const res = await fetch(`${API_BASE}/admin/unsubscribe/${userId}?t=${encodeURIComponent(token)}`, {
      method: "POST",
    });
    setState(res.ok ? "done" : "invalid");
  };

  return (
    <main className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">Email preferences</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-50">Weekly summary</h1>

      {state === "loading" && (
        <p className="mt-8 text-sm text-slate-500">Checking…</p>
      )}
      {state === "invalid" && (
        <div className="mt-8 space-y-3 text-sm text-slate-400">
          <p>This unsubscribe link is invalid or expired.</p>
          <p>
            If you want to stop the weekly emails, sign in and email{" "}
            <a href="mailto:goldenkapparu@gmail.com" className="text-cyan-400 hover:underline">
              goldenkapparu@gmail.com
            </a>.
          </p>
        </div>
      )}
      {state === "confirm" && (
        <div className="mt-8 space-y-4">
          <p className="text-sm text-slate-300">
            Stop sending the weekly summary email to{" "}
            <span className="font-medium text-slate-100">{email}</span>?
          </p>
          <button
            type="button"
            onClick={doUnsubscribe}
            className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
          >
            Yes, unsubscribe
          </button>
          <p className="text-xs text-slate-500">
            You&apos;ll keep all your account data and can resubscribe anytime by emailing us.
          </p>
        </div>
      )}
      {state === "already" && (
        <p className="mt-8 text-sm text-slate-400">
          <span className="text-slate-200">{email}</span> is already unsubscribed from the weekly summary.
        </p>
      )}
      {state === "done" && (
        <p className="mt-8 text-sm text-emerald-300">
          Done. {email} won&apos;t receive the weekly summary anymore.
        </p>
      )}

      <p className="mt-12 text-xs text-slate-600">
        <Link href="/" className="hover:text-slate-400">← Back to ExTaSy</Link>
      </p>
    </main>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-md px-4 py-16 sm:px-6"><p className="text-sm text-slate-500">Loading…</p></main>}>
      <UnsubscribeInner />
    </Suspense>
  );
}
