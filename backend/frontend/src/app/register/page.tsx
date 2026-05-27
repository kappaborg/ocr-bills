"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { register } from "@/lib/api";
import { getAccessToken, setAccessToken } from "@/lib/auth";

function passwordStrength(pw: string): { level: 0 | 1 | 2; label: string; color: string } {
  if (pw.length < 8) return { level: 0, label: "Weak", color: "bg-red-500" };
  const hasMix = /[A-Z]/.test(pw) && /[0-9]/.test(pw);
  const hasSymbol = /[^A-Za-z0-9]/.test(pw);
  if (pw.length >= 10 && (hasMix || hasSymbol))
    return { level: 2, label: "Strong", color: "bg-emerald-500" };
  return { level: 1, label: "Fair", color: "bg-amber-400" };
}

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getAccessToken()) router.replace("/dashboard");
  }, [router]);

  const strength = passwordStrength(password);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setPwError("Password must be at least 8 characters.");
      return;
    }
    setPwError(null);
    setError(null);
    setLoading(true);
    try {
      const res = await register(email, password);
      setAccessToken(res.access_token);
      router.replace("/onboarding");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Register failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-4 py-12">
      <div className="glass-panel w-full max-w-md p-8">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
          Welcome
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-50">Create account</h1>
        <p className="mt-1 text-sm text-slate-400">
          Start scanning receipts in seconds.
        </p>

        <form onSubmit={onSubmit} className="mt-8 space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-slate-300">Email</span>
            <input
              className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-slate-100 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              autoComplete="email"
              required
            />
          </label>

          <div>
            <label className="block">
              <span className="text-sm font-medium text-slate-300">Password</span>
              <input
                className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-slate-100 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
              />
            </label>

            {password.length > 0 && (
              <div className="mt-2">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className={`h-1 flex-1 rounded-full transition-all ${
                        i <= strength.level ? strength.color : "bg-white/10"
                      }`}
                    />
                  ))}
                </div>
                <p className={`mt-1 text-xs ${
                  strength.level === 2 ? "text-emerald-400" :
                  strength.level === 1 ? "text-amber-400" : "text-red-400"
                }`}>
                  {strength.label}
                </p>
              </div>
            )}

            {pwError && (
              <p className="mt-1 text-xs text-red-400">{pwError}</p>
            )}
          </div>

          {error ? <p className="text-sm text-red-300">{error}</p> : null}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 hover:brightness-110 disabled:opacity-50"
          >
            {loading ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-cyan-400 hover:text-cyan-300">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
