import { ReactNode } from "react";

/** Full-viewport futuristic backdrop (fixes dark-mode / white-card contrast issues). */
export function AppBackground({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-app antialiased selection:bg-cyan-500/30 selection:text-white" style={{ color: "var(--text-primary)" }}>
      <div className="pointer-events-none fixed inset-0 bg-grid opacity-40" aria-hidden />
      <div className="pointer-events-none fixed inset-0 bg-gradient-to-b from-cyan-500/[0.07] via-transparent to-emerald-500/[0.05]" aria-hidden />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
