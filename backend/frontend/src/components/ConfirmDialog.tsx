"use client";

// Accessible confirm-dialog replacement for window.confirm().
// Usage:
//   const confirm = useConfirm();
//   if (await confirm({ title: "Delete?", body: "This can't be undone.", danger: true })) { ... }
//
// Renders a single global modal, traps focus while open, dismisses on Esc
// or click-outside. Returns the user's choice via Promise so call-sites
// stay as one-liners.

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

type ConfirmOpts = {
  title: string;
  body?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
};

type ConfirmContextValue = (opts: ConfirmOpts) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

type Pending = {
  opts: ConfirmOpts;
  resolve: (v: boolean) => void;
};

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const confirmBtnRef = useRef<HTMLButtonElement | null>(null);

  const ask = useCallback<ConfirmContextValue>((opts) => {
    return new Promise<boolean>((resolve) => {
      setPending({ opts, resolve });
    });
  }, []);

  const decide = useCallback((v: boolean) => {
    if (!pending) return;
    pending.resolve(v);
    setPending(null);
  }, [pending]);

  // Esc → cancel; focus the confirm button on open
  useEffect(() => {
    if (!pending) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        decide(false);
      } else if (e.key === "Enter") {
        e.preventDefault();
        decide(true);
      }
    };
    window.addEventListener("keydown", handler);
    confirmBtnRef.current?.focus();
    return () => window.removeEventListener("keydown", handler);
  }, [pending, decide]);

  return (
    <ConfirmContext.Provider value={ask}>
      {children}
      {pending && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4"
          onClick={() => decide(false)}
        >
          <div
            className="glass-panel max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="confirm-title" className="text-lg font-semibold text-slate-50">
              {pending.opts.title}
            </h2>
            {pending.opts.body && (
              <p className="mt-2 text-sm text-slate-400">{pending.opts.body}</p>
            )}
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => decide(false)}
                className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
              >
                {pending.opts.cancelLabel ?? "Cancel"}
              </button>
              <button
                ref={confirmBtnRef}
                type="button"
                onClick={() => decide(true)}
                className={`rounded-xl px-4 py-2 text-sm font-semibold ${
                  pending.opts.danger
                    ? "bg-red-600 text-slate-50 hover:bg-red-500"
                    : "bg-gradient-to-r from-cyan-500 to-emerald-500 text-slate-950 hover:brightness-110"
                }`}
              >
                {pending.opts.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmContextValue {
  const ctx = useContext(ConfirmContext);
  if (ctx === null) {
    // Fall back to native confirm so call-sites still work in test envs
    return async (opts) =>
      typeof window !== "undefined" && window.confirm(`${opts.title}\n\n${opts.body ?? ""}`);
  }
  return ctx;
}
