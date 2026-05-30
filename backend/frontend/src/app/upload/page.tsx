"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getAccessToken } from "@/lib/auth";
import { getMyBilling, uploadReceipts, type BillingMe } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const token = getAccessToken();
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Soft-wall modal when the user hits their quota (server returns 402)
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [quotaBlocked, setQuotaBlocked] = useState(false);

  // Pre-fetch billing so we can show "X / 20 left this month" inline
  useEffect(() => {
    if (token) getMyBilling(token).then(setBilling).catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  // Build and revoke object URLs when files change
  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  const canUpload = useMemo(() => Boolean(token) && files.length > 0, [token, files.length]);

  const onFilesChange = (list: FileList | null) => {
    if (!list) { setFiles([]); return; }
    setFiles(Array.from(list));
    setError(null);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const onUpload = async () => {
    if (!token) return router.replace("/login");
    if (!files.length) return;
    setLoading(true);
    setError(null);
    setQuotaBlocked(false);
    try {
      const res = await uploadReceipts(files, token);
      const receiptId = res.results[0]?.receipt_id;
      if (!receiptId) throw new Error("No receipt returned from upload");
      router.push(`/receipt/${receiptId}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      // Quota-exhausted message comes from the backend with the word "limit".
      // Intercept it and show the upgrade modal instead of a generic red alert.
      if (msg.toLowerCase().includes("receipt limit reached")) {
        setQuotaBlocked(true);
        // Refresh billing snapshot so the modal can show the exact usage.
        if (token) getMyBilling(token).then(setBilling).catch(() => {});
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-xl px-4 py-8 sm:px-6 sm:py-10">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
        Scan
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
        Drop your receipt
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        JPG or PNG — we run OCR, detect language, then you review before saving.
      </p>

      {error ? (
        <div
          role="alert"
          className="mt-6 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200"
        >
          {error}
        </div>
      ) : null}

      <div className="glass-panel mt-8 space-y-6 p-6">
        <label className="block">
          <span className="text-sm font-medium text-slate-300">Images</span>
          <input
            type="file"
            accept="image/jpeg,image/png"
            multiple
            onChange={(e) => onFilesChange(e.target.files)}
            className="mt-3 block w-full cursor-pointer rounded-xl border border-dashed border-white/20 bg-slate-950/50 px-4 py-8 text-center text-sm text-slate-400 file:mr-4 file:cursor-pointer file:rounded-lg file:border-0 file:bg-cyan-500/20 file:px-4 file:py-2 file:text-sm file:font-medium file:text-cyan-200"
          />
          <p className="mt-2 text-xs text-slate-500">
            PDF support is coming — use photos for now.
          </p>
        </label>

        {/* File previews */}
        {files.length > 0 && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {files.map((file, i) => (
              <div key={i} className="group relative overflow-hidden rounded-xl border border-white/10 bg-slate-900/60">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previews[i]}
                  alt={file.name}
                  className="h-28 w-full object-cover"
                />
                <p className="truncate px-2 py-1.5 text-[11px] text-slate-400">{file.name}</p>
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-950/80 text-slate-400 opacity-0 transition group-hover:opacity-100 hover:text-red-300"
                  aria-label="Remove file"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          disabled={!canUpload || loading}
          onClick={onUpload}
          className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Uploading…" : "Upload & review"}
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() => router.push("/dashboard")}
          className="w-full rounded-xl border border-white/15 bg-white/5 py-3 text-sm font-medium text-slate-200 hover:bg-white/10 disabled:opacity-50"
        >
          Back to dashboard
        </button>
      </div>

      {/* Soft-wall: show usage hint inline + full upgrade modal at 100% */}
      {billing && billing.plan === "free" && billing.usage.receipts_quota > 0 && (
        <p className="mt-4 text-center text-xs text-slate-500">
          {billing.usage.receipts_used} of {billing.usage.receipts_quota} free receipts used this month.
          {" "}
          <button onClick={() => router.push("/pricing")} className="text-cyan-400 hover:text-cyan-300">
            See Pro for unlimited →
          </button>
        </p>
      )}

      {quotaBlocked && billing && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4"
          onClick={() => setQuotaBlocked(false)}
        >
          <div
            className="glass-panel relative max-w-md w-full p-6 sm:p-8"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setQuotaBlocked(false)}
              className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
              aria-label="Close"
            >
              ×
            </button>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-amber-300/90">
              Out of free uploads
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50">
              You&apos;ve used all {billing.usage.receipts_quota} free receipts this month.
            </h2>
            <p className="mt-3 text-sm text-slate-400">
              Quota resets on the 1st of next month. Or upgrade now and:
            </p>
            <ul className="mt-3 space-y-1.5 text-sm text-slate-300">
              <li className="flex items-start gap-2"><span className="mt-0.5 text-cyan-400">✓</span> 500 receipts/month on Pro ($4.99)</li>
              <li className="flex items-start gap-2"><span className="mt-0.5 text-cyan-400">✓</span> PDF / QuickBooks / Xero exports</li>
              <li className="flex items-start gap-2"><span className="mt-0.5 text-cyan-400">✓</span> Monthly budgets + recurring detection</li>
              <li className="flex items-start gap-2"><span className="mt-0.5 text-emerald-400">✓</span> Unlimited on Business ($19.99) + household sharing</li>
            </ul>
            <div className="mt-6 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => router.push("/pricing")}
                className="flex-1 rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2.5 text-sm font-semibold text-slate-950 shadow-md shadow-cyan-500/25 hover:brightness-110"
              >
                See plans
              </button>
              <button
                type="button"
                onClick={() => setQuotaBlocked(false)}
                className="rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-200 hover:bg-white/10"
              >
                Maybe later
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
