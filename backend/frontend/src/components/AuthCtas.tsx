"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth";

/**
 * Client island for the landing page's auth-aware buttons. The page itself
 * is a server component (SEO + fast LCP); only these buttons need
 * localStorage, so they hydrate separately. Until mount we render the
 * logged-out variant — matches SSR output, no hydration mismatch.
 */
function useAuthed(): boolean {
  const [authed, setAuthed] = useState(false);
  useEffect(() => {
    setAuthed(Boolean(getAccessToken()));
  }, []);
  return authed;
}

const PRIMARY =
  "rounded-xl px-6 py-3 text-sm font-semibold transition bg-gradient-to-r from-cyan-500 to-emerald-500 text-slate-950 shadow-lg shadow-cyan-500/25 hover:brightness-110";
const SECONDARY =
  "rounded-xl px-6 py-3 text-sm font-semibold transition border border-white/15 bg-white/5 text-slate-200 hover:bg-white/10";

export function HeaderAuthCta() {
  const authed = useAuthed();
  return authed ? (
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
  );
}

export function HeroCtas() {
  const authed = useAuthed();
  return authed ? (
    <>
      <Link href="/dashboard" className={PRIMARY}>Open dashboard</Link>
      <Link href="/upload" className={SECONDARY}>New scan</Link>
    </>
  ) : (
    <>
      <Link href="/register" className={PRIMARY}>Try it free</Link>
      <Link href="/pricing" className={SECONDARY}>See pricing</Link>
    </>
  );
}

export function BottomCta() {
  const authed = useAuthed();
  return authed ? (
    <Link href="/dashboard" className={PRIMARY}>Open dashboard</Link>
  ) : (
    <Link href="/register" className={PRIMARY}>Try it free</Link>
  );
}
