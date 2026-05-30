"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/inbox", label: "Inbox" },
  { href: "/upload", label: "Upload" },
  { href: "/scan", label: "Scan" },
  { href: "/inventory", label: "Inventory" },
  { href: "/need-to-buy", label: "Need to buy" },
  { href: "/reconcile", label: "Reconcile" },
  { href: "/pricing", label: "Pricing" },
  { href: "/settings", label: "Settings" },
];

// Routes that present their own header (landing) or are pre-login flows where
// the app-shell nav would be confusing. Returning null hides the global nav.
const STANDALONE_ROUTES = new Set([
  "/",
  "/login",
  "/register",
  "/onboarding",
  "/pricing",          // pricing page is a marketing surface even when logged in
]);

export function TopNav() {
  const pathname = usePathname();
  if (STANDALONE_ROUTES.has(pathname || "/")) return null;

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="group flex items-center gap-2" title="ExTaSy — Expense Tracking System">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-emerald-500 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/20">
            ◈
          </span>
          <span className="font-semibold tracking-tight text-slate-100">
            Ex<span className="text-cyan-400">TaSy</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1 overflow-x-auto sm:gap-2">
          {links.map((l) => {
            const active =
              pathname === l.href ||
              (l.href !== "/" && pathname.startsWith(l.href + "/"));
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-white/10 text-cyan-300 underline decoration-cyan-400/50 underline-offset-4"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
