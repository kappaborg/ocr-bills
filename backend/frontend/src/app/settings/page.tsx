"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import { getMe, getMyBilling, openCustomerPortal, updateProfile, type BillingMe } from "@/lib/api";

function passwordStrength(pw: string): { level: 0 | 1 | 2; label: string; color: string } {
  if (pw.length < 8) return { level: 0, label: "Weak", color: "bg-red-500" };
  const hasMix = /[A-Z]/.test(pw) && /[0-9]/.test(pw);
  const hasSymbol = /[^A-Za-z0-9]/.test(pw);
  if (pw.length >= 10 && (hasMix || hasSymbol))
    return { level: 2, label: "Strong", color: "bg-emerald-500" };
  return { level: 1, label: "Fair", color: "bg-amber-400" };
}

export default function SettingsPage() {
  const router = useRouter();
  const token = getAccessToken();

  const [email, setEmail] = useState("");
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) { router.replace("/login"); return; }
    getMe(token).then((me) => setEmail(me.email)).catch(() => {});
    getMyBilling(token).then(setBilling).catch(() => {});
  }, [token, router]);

  const handleManageBilling = async () => {
    if (!token) return;
    setPortalLoading(true);
    try {
      const r = await openCustomerPortal(token);
      window.location.href = r.portal_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open billing portal");
    } finally {
      setPortalLoading(false);
    }
  };

  const strength = passwordStrength(newPw);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPw.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPw !== confirmPw) {
      setError("Passwords don't match.");
      return;
    }

    setSaving(true);
    try {
      await updateProfile(currentPw, newPw, token!);
      setSuccess("Password updated successfully.");
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="mx-auto max-w-xl px-4 py-8 sm:px-6 sm:py-10">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
        Account
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">Settings</h1>
      <p className="mt-2 text-sm text-slate-400">Manage your account preferences.</p>

      <div className="mt-8 space-y-6">
        {/* Account info */}
        <section className="glass-panel p-6">
          <h2 className="text-base font-semibold text-slate-50">Account</h2>
          <div className="mt-4">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Email</p>
            <p className="mt-1 text-sm text-slate-200">{email || "—"}</p>
          </div>
        </section>

        {/* Subscription */}
        <section className="glass-panel p-6">
          <h2 className="text-base font-semibold text-slate-50">Subscription</h2>
          {billing ? (
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Current plan</p>
                  <p className="mt-1 text-sm font-medium text-slate-100">
                    <span className={
                      billing.plan === "free" ? "text-slate-300"
                        : billing.plan === "pro" ? "text-cyan-300" : "text-emerald-300"
                    }>
                      {billing.plan.toUpperCase()}
                    </span>
                    {billing.status !== "active" && (
                      <span className="ml-2 text-xs text-amber-300">({billing.status})</span>
                    )}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs uppercase tracking-wider text-slate-500">This month</p>
                  <p className="mt-1 text-sm font-mono tabular-nums text-slate-100">
                    {billing.usage.receipts_quota === 0
                      ? `${billing.usage.receipts_used} (unlimited)`
                      : `${billing.usage.receipts_used} / ${billing.usage.receipts_quota}`}
                  </p>
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                {billing.plan === "free" ? (
                  <button
                    type="button"
                    onClick={() => router.push("/pricing")}
                    className="rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:brightness-110"
                  >
                    Upgrade
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={portalLoading}
                    onClick={handleManageBilling}
                    className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/10 disabled:opacity-50"
                  >
                    {portalLoading ? "Opening…" : "Manage billing"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => router.push("/pricing")}
                  className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
                >
                  See plans
                </button>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">Loading…</p>
          )}
        </section>

        {/* Change password */}
        <section className="glass-panel p-6">
          <h2 className="text-base font-semibold text-slate-50">Change password</h2>

          {success && (
            <div className="mt-4 rounded-xl border border-emerald-500/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-300">
              {success}
            </div>
          )}
          {error && (
            <div className="mt-4 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <form onSubmit={onSubmit} className="mt-5 space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-slate-300">Current password</span>
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                autoComplete="current-password"
                required
                className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-slate-100 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20"
              />
            </label>

            <div>
              <label className="block">
                <span className="text-sm font-medium text-slate-300">New password</span>
                <input
                  type="password"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  autoComplete="new-password"
                  required
                  minLength={8}
                  className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-slate-100 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20"
                />
              </label>
              {newPw.length > 0 && (
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
            </div>

            <label className="block">
              <span className="text-sm font-medium text-slate-300">Confirm new password</span>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                autoComplete="new-password"
                required
                className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-slate-100 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20"
              />
              {confirmPw.length > 0 && newPw !== confirmPw && (
                <p className="mt-1 text-xs text-red-400">Passwords don&apos;t match</p>
              )}
            </label>

            <button
              type="submit"
              disabled={saving}
              className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 hover:brightness-110 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Update password"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
