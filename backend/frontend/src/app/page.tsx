"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getAccessToken, clearAccessToken } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setHasToken(Boolean(getAccessToken()));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-24">
      <div className="text-center">
        <p className="text-xs font-medium uppercase tracking-[0.25em] text-cyan-400/90">
          Receipt intelligence
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-50 sm:text-5xl">
          Scan{" "}
          <span className="bg-gradient-to-r from-cyan-300 to-emerald-400 bg-clip-text text-transparent">
            smarter
          </span>
          .
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-lg text-slate-400">
          OCR + language detection, review in a clear UI, then see your spending
          patterns — built for real receipts, not spreadsheets.
        </p>
      </div>

      <div className="mt-12 flex flex-wrap justify-center gap-3">
        {hasToken ? (
          <>
            <button
              type="button"
              onClick={() => router.push("/dashboard")}
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-8 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/25 transition hover:brightness-110"
            >
              Open dashboard
            </button>
            <button
              type="button"
              onClick={() => router.push("/upload")}
              className="rounded-xl border border-white/15 bg-white/5 px-8 py-3 text-sm font-medium text-slate-200 hover:bg-white/10"
            >
              New scan
            </button>
            <button
              type="button"
              onClick={() => {
                clearAccessToken();
                setHasToken(false);
                router.refresh();
              }}
              className="rounded-xl px-6 py-3 text-sm text-slate-500 hover:text-slate-300"
            >
              Log out
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => router.push("/login")}
              className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-8 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/25 hover:brightness-110"
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => router.push("/register")}
              className="rounded-xl border border-white/15 bg-white/5 px-8 py-3 text-sm font-medium text-slate-200 hover:bg-white/10"
            >
              Register
            </button>
          </>
        )}
      </div>

      <p className="mt-16 text-center text-xs text-slate-600">
        API{" "}
        <span className="font-mono text-slate-500">
          {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}
        </span>
      </p>
    </main>
  );
}
