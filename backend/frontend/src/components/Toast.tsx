"use client";

// Global toast queue.
//
// Why hand-rolled: only ~3KB, no extra deps, no animation library, full
// control over styling. If a fancier need arises (action buttons, progress
// toasts), swap to react-hot-toast later.

import { createContext, useCallback, useContext, useEffect, useState } from "react";

type ToastKind = "info" | "success" | "error";

type Toast = {
  id: number;
  kind: ToastKind;
  message: string;
  ttlMs: number;
};

type ToastContextValue = {
  push: (message: string, opts?: { kind?: ToastKind; ttlMs?: number }) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

let _toastIdCounter = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback<ToastContextValue["push"]>((message, opts) => {
    const id = ++_toastIdCounter;
    const kind = opts?.kind ?? "info";
    const ttlMs = opts?.ttlMs ?? (kind === "error" ? 7000 : 4000);
    setToasts((prev) => [...prev, { id, kind, message, ttlMs }]);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Auto-dismiss
  useEffect(() => {
    if (toasts.length === 0) return;
    const timers = toasts.map((t) =>
      setTimeout(() => dismiss(t.id), t.ttlMs),
    );
    return () => timers.forEach(clearTimeout);
  }, [toasts, dismiss]);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      {/* Live region for assistive tech — toasts announce themselves */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => dismiss(t.id)}
            className={`pointer-events-auto cursor-pointer rounded-xl border px-4 py-3 text-sm shadow-xl backdrop-blur transition ${
              t.kind === "success"
                ? "border-emerald-500/40 bg-emerald-950/80 text-emerald-100"
                : t.kind === "error"
                  ? "border-red-500/50 bg-red-950/80 text-red-100"
                  : "border-cyan-500/30 bg-slate-950/90 text-slate-100"
            }`}
          >
            <p>{t.message}</p>
            <p className="mt-1 text-[10px] uppercase tracking-wider opacity-60">
              click to dismiss
            </p>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (ctx === null) {
    // In a test or pre-mount situation, no-op rather than crash.
    return {
      push: (msg) => {
        if (typeof console !== "undefined") console.warn("[toast outside provider]", msg);
      },
    };
  }
  return ctx;
}
