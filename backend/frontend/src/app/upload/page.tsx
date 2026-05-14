"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getAccessToken } from "@/lib/auth";
import { uploadReceipts } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const token = getAccessToken();
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const canUpload = useMemo(() => Boolean(token) && files.length > 0, [token, files.length]);

  const onFilesChange = (list: FileList | null) => {
    if (!list) return setFiles([]);
    setFiles(Array.from(list));
    setError(null);
  };

  const onUpload = async () => {
    if (!token) return router.replace("/login");
    if (!files.length) return;
    setLoading(true);
    setError(null);
    try {
      const res = await uploadReceipts(files, token);
      const receiptId = res.results[0]?.receipt_id;
      if (!receiptId) throw new Error("No receipt returned from upload");
      router.push(`/receipt/${receiptId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
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

        {files.length > 0 ? (
          <p className="text-sm text-slate-400">
            <span className="font-mono text-cyan-300">{files.length}</span> file
            {files.length === 1 ? "" : "s"} selected
          </p>
        ) : null}

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
    </main>
  );
}
