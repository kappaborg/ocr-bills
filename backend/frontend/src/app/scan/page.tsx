"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import { createReceiptFromFrame, livePreviewReceipt } from "@/lib/api";
import type { ReceiptOut } from "@/lib/types";

type ScanState = "idle" | "scanning" | "detected" | "no-text";

export default function ScanPage() {
  const router = useRouter();
  // Defer the auth-token read until after mount — getAccessToken() touches
  // localStorage and would mismatch the SSR shell otherwise. Same pattern as
  // /dashboard.
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setToken(getAccessToken());
    setMounted(true);
  }, []);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Use a ref for in-flight status so it never triggers effect re-runs.
  const isSendingRef = useRef(false);
  const failCountRef = useRef(0);

  const [preview, setPreview] = useState<ReceiptOut | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [scanState, setScanState] = useState<ScanState>("idle");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Start camera stream.
  useEffect(() => {
    if (!mounted) return;            // wait for first-mount token read
    if (!token) {
      router.replace("/login");
      return;
    }

    let stream: MediaStream | null = null;

    const startCamera = () => {
      navigator.mediaDevices
        .getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false })
        .then((s) => {
          stream = s;
          if (videoRef.current) {
            videoRef.current.srcObject = s;
            videoRef.current.play().catch((err: Error) => {
              setFatalError(`Camera failed to start: ${err.message}`);
            });
          }
          setIsStreaming(true);
          setFatalError(null);
        })
        .catch((err: Error) => {
          const isPermission = err.name === "NotAllowedError" || err.name === "PermissionDeniedError";
          if (isPermission) {
            setFatalError(
              "camera_denied"
            );
          } else {
            setFatalError(`Camera error: ${err.message}. Try reloading the page.`);
          }
        });
    };

    startCamera();

    return () => {
      stream?.getTracks().forEach((t) => t.stop());
      setIsStreaming(false);
    };
  }, [router, token, mounted]);

  // OCR polling loop — dep array intentionally excludes isSending (we use a ref).
  useEffect(() => {
    if (!isStreaming || !token) return;

    let cancelled = false;

    const tick = async () => {
      if (cancelled) return;

      // Skip this tick if a request is already in-flight.
      if (isSendingRef.current) {
        window.setTimeout(tick, 500);
        return;
      }

      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) {
        window.setTimeout(tick, 800);
        return;
      }

      // Wait until the video stream has actual dimensions.
      const w = video.videoWidth;
      const h = video.videoHeight;
      if (!w || !h) {
        window.setTimeout(tick, 800);
        return;
      }

      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, w, h);

      const blob: Blob | null = await new Promise((resolve) =>
        canvas.toBlob((b) => resolve(b), "image/jpeg", 0.95)
      );
      if (!blob || cancelled) return;

      isSendingRef.current = true;
      setScanState("scanning");

      try {
        const receipt = await livePreviewReceipt(blob, token);
        if (!cancelled) {
          setPreview(receipt);
          setScanState("detected");
          failCountRef.current = 0;
        }
      } catch {
        // OCR failure is completely normal — the receipt may not be in frame yet,
        // or the image is blurry. Don't surface this as a UI error; just keep scanning.
        if (!cancelled) {
          failCountRef.current += 1;
          // Only show "no text" after several consecutive misses so the UI isn't noisy.
          if (failCountRef.current > 4) setScanState("no-text");
        }
      } finally {
        isSendingRef.current = false;
        if (!cancelled) window.setTimeout(tick, 1200);
      }
    };

    const id = window.setTimeout(tick, 800);
    return () => {
      cancelled = true;
      window.clearTimeout(id);
    };
  }, [isStreaming, token]); // ← isSending intentionally omitted (we use a ref)

  const onSave = async () => {
    if (!token) return router.replace("/login");
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    setIsSaving(true);
    setFatalError(null);
    try {
      canvas.width = video.videoWidth || 1280;
      canvas.height = video.videoHeight || 720;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas not available");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob: Blob | null = await new Promise((resolve) =>
        canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92)
      );
      if (!blob) throw new Error("Failed to capture frame");

      const res = await createReceiptFromFrame(blob, token);
      router.push(`/receipt/${res.receipt_id}`);
    } catch (err) {
      setFatalError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  };

  const scanLabel: Record<ScanState, string> = {
    idle: "Starting camera…",
    scanning: "Scanning…",
    detected: "Receipt detected",
    "no-text": "Point at your receipt",
  };

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400/90">
        Live scan
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-50">
        Point at your receipt
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        We continuously OCR the frame. When we lock on, hit Save.
      </p>

      {fatalError && (
        <div
          role="alert"
          className="mt-4 rounded-xl border border-red-500/40 bg-red-950/40 px-4 py-4 text-sm text-red-200"
        >
          {fatalError === "camera_denied" ? (
            <div className="space-y-2">
              <p className="font-medium">Camera access is required for scanning.</p>
              <p className="text-xs text-red-300/80">
                On iPhone: Settings → Safari → Camera → Allow.<br />
                On Android: tap the camera icon in the address bar.<br />
                Then reload this page.
              </p>
              <button
                type="button"
                onClick={() => {
                  setFatalError(null);
                  setIsStreaming(false);
                  // Re-trigger camera by re-running the effect via a state bump
                  window.location.reload();
                }}
                className="mt-1 rounded-lg border border-red-400/40 px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-900/40"
              >
                Try again
              </button>
            </div>
          ) : (
            fatalError
          )}
        </div>
      )}

      <section className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        {/* Camera feed */}
        <div className="overflow-hidden rounded-2xl border border-white/15 bg-slate-950/60">
          <div className="relative aspect-[9/16] w-full bg-slate-900/80">
            <video ref={videoRef} muted playsInline className="h-full w-full object-contain" />

            {/* Receipt guide frame */}
            <div className="pointer-events-none absolute inset-6 rounded-2xl border border-cyan-400/40 shadow-[0_0_40px_rgba(34,211,238,0.35)]" />

            {/* Scan state badge */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap">
              <span
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium backdrop-blur-sm ${
                  scanState === "detected"
                    ? "bg-emerald-500/30 text-emerald-200 ring-1 ring-emerald-400/40"
                    : scanState === "no-text"
                    ? "bg-amber-500/20 text-amber-200 ring-1 ring-amber-400/30"
                    : "bg-slate-900/70 text-slate-400 ring-1 ring-white/10"
                }`}
              >
                {scanState === "scanning" && (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
                )}
                {scanState === "detected" && (
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                )}
                {scanLabel[scanState]}
              </span>
            </div>
          </div>
          <canvas ref={canvasRef} className="hidden" />
        </div>

        {/* Preview panel */}
        <div className="glass-panel space-y-4 p-5">
          <h2 className="text-sm font-semibold text-slate-100">Detected summary</h2>

          {preview ? (
            <div className="space-y-3 text-sm text-slate-200">
              {/* Header */}
              <div className="rounded-lg bg-slate-900/70 px-3 py-2 text-xs text-slate-300">
                <div className="flex flex-wrap items-center justify-between gap-1">
                  <span className="font-semibold">{preview.store_name || "Store ?"}</span>
                  <span className="text-slate-400">{preview.detected_language ?? "lang ?"}</span>
                </div>
                <div className="mt-1 flex items-baseline justify-between gap-2">
                  <span className="text-slate-400">
                    {preview.receipt_date
                      ? new Date(preview.receipt_date).toLocaleDateString()
                      : "Date ?"}
                  </span>
                  <span className="font-mono text-emerald-300">
                    {preview.total_amount != null
                      ? `${preview.total_amount.toFixed(2)} ${preview.currency ?? ""}`
                      : "Total ?"}
                  </span>
                </div>
              </div>

              {/* Items list */}
              <div className="max-h-72 space-y-1 overflow-y-auto rounded-lg bg-slate-950/60 p-2">
                {preview.items.length > 0 ? (
                  preview.items.map((it) => (
                    <div
                      key={it.id}
                      className="flex items-center justify-between gap-3 rounded-lg bg-slate-900/80 px-3 py-1.5 text-xs"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-slate-100">{it.item_name}</p>
                        <p className="mt-0.5 text-[11px] text-slate-400">
                          {it.category_name ?? "Uncategorized"}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="font-mono text-emerald-300">{it.item_price.toFixed(2)}</p>
                        <p className="mt-0.5 text-[10px] text-slate-500">
                          {Math.round((it.confidence_score ?? 0) * 100)}%
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="px-1 py-2 text-xs text-slate-500">
                    Items will appear here once OCR locks on.
                  </p>
                )}
              </div>

              <button
                type="button"
                disabled={isSaving}
                onClick={onSave}
                className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 py-2.5 text-xs font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSaving ? "Saving…" : "Save receipt"}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-slate-500">
                Hold the receipt steady in the frame. We&apos;ll detect text automatically.
              </p>
              {/* Save without preview (for when OCR is slow but user wants to capture) */}
              <button
                type="button"
                disabled={isSaving || !isStreaming}
                onClick={onSave}
                className="w-full rounded-xl border border-white/15 bg-white/5 py-2.5 text-xs font-medium text-slate-300 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isSaving ? "Saving…" : "Capture now anyway"}
              </button>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
