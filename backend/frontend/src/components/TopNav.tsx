"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { clearAccessToken } from "@/lib/auth";

// ── Two-level navigation ─────────────────────────────────────────────────
// Three primary tabs. Most secondary actions live in dropdowns under them.
// Account-y items (Pricing, Settings, Logout) collapse into the avatar menu.
//
// Why this split:
//   Dashboard → the home view (spending pulse, budgets, insights, recurring).
//   Receipts  → everything about creating / reviewing individual receipts.
//   Insights  → everything that operates on the body of confirmed receipts.

type SubLink = { href: string; label: string; hint?: string };
type PrimaryTab = {
  href: string;            // route the tab itself navigates to
  label: string;
  match: string[];         // pathname prefixes that should highlight this tab
  sub?: SubLink[];         // dropdown menu (optional)
};

const TABS: PrimaryTab[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    match: ["/dashboard"],
  },
  {
    href: "/inbox",
    label: "Receipts",
    match: ["/inbox", "/upload", "/scan", "/receipt"],
    sub: [
      { href: "/inbox",  label: "Inbox",       hint: "Review parsed receipts" },
      { href: "/upload", label: "Upload",      hint: "Drop a photo" },
      { href: "/scan",   label: "Scan",        hint: "Use the camera" },
    ],
  },
  {
    href: "/inventory",
    label: "Insights",
    match: ["/inventory", "/need-to-buy", "/reconcile"],
    sub: [
      { href: "/inventory",   label: "Inventory",   hint: "Products you've bought" },
      { href: "/need-to-buy", label: "Need to buy", hint: "Forecast restocks" },
      { href: "/reconcile",   label: "Reconcile",   hint: "Match a bank CSV" },
    ],
  },
];

const STANDALONE_ROUTES = new Set([
  "/",
  "/login",
  "/register",
  "/onboarding",
  "/pricing",          // pricing page is a marketing surface even when logged in
  "/billing/success",
]);

function isPathInMatches(path: string, matches: string[]) {
  return matches.some((m) => path === m || path.startsWith(m + "/"));
}

export function TopNav() {
  const pathname = usePathname() || "/";
  const router = useRouter();

  // Which tab's dropdown is open (mouseenter or focus). null = none.
  const [openTab, setOpenTab] = useState<string | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement | null>(null);

  // Click-outside for the account menu (the tab popovers are hover-based)
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(e.target as Node)) {
        setAccountOpen(false);
      }
    };
    if (accountOpen) document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [accountOpen]);

  if (STANDALONE_ROUTES.has(pathname)) return null;

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2" title="ExTaSy — Expense Tracking System">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-emerald-500 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/20">
            ◈
          </span>
          <span className="hidden font-semibold tracking-tight text-slate-100 sm:inline">
            Ex<span className="text-cyan-400">TaSy</span>
          </span>
        </Link>

        {/* Primary tabs with hover-popover sub-menus */}
        <nav className="flex flex-1 items-center justify-center gap-1 sm:gap-2">
          {TABS.map((tab) => {
            const active = isPathInMatches(pathname, tab.match);
            const isOpen = openTab === tab.href && Boolean(tab.sub);
            return (
              <div
                key={tab.href}
                className="relative"
                onMouseEnter={() => setOpenTab(tab.href)}
                onMouseLeave={() => setOpenTab(null)}
              >
                <Link
                  href={tab.href}
                  className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-white/10 text-cyan-300"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                  }`}
                >
                  {tab.label}
                  {tab.sub && (
                    <span className="text-[10px] text-slate-500" aria-hidden>▾</span>
                  )}
                </Link>

                {isOpen && tab.sub && (
                  <div className="absolute left-1/2 top-full z-50 mt-1 w-60 -translate-x-1/2 overflow-hidden rounded-xl border border-white/10 bg-slate-950/95 shadow-xl backdrop-blur">
                    <ul>
                      {tab.sub.map((s) => {
                        const subActive = pathname === s.href;
                        return (
                          <li key={s.href}>
                            <Link
                              href={s.href}
                              onClick={() => setOpenTab(null)}
                              className={`block px-4 py-2.5 transition ${
                                subActive ? "bg-cyan-500/10 text-cyan-200" : "text-slate-200 hover:bg-white/5"
                              }`}
                            >
                              <span className="block text-sm font-medium">{s.label}</span>
                              {s.hint && <span className="block text-[11px] text-slate-500">{s.hint}</span>}
                            </Link>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Account menu — Pricing / Settings / Logout collapsed under the avatar */}
        <div className="relative" ref={accountMenuRef}>
          <button
            type="button"
            aria-label="Account menu"
            onClick={() => setAccountOpen((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-slate-900/60 text-sm text-slate-200 hover:border-cyan-500/40 hover:bg-cyan-500/10"
          >
            ⋯
          </button>
          {accountOpen && (
            <div className="absolute right-0 top-full z-50 mt-1 w-52 overflow-hidden rounded-xl border border-white/10 bg-slate-950/95 shadow-xl backdrop-blur">
              <ul>
                <li>
                  <Link href="/pricing" onClick={() => setAccountOpen(false)} className="block px-4 py-2.5 text-sm text-slate-200 hover:bg-white/5">
                    Pricing
                  </Link>
                </li>
                <li>
                  <Link href="/settings" onClick={() => setAccountOpen(false)} className="block px-4 py-2.5 text-sm text-slate-200 hover:bg-white/5">
                    Settings
                  </Link>
                </li>
                <li className="border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => {
                      clearAccessToken();
                      setAccountOpen(false);
                      router.replace("/login");
                    }}
                    className="block w-full px-4 py-2.5 text-left text-sm text-slate-300 hover:bg-red-950/40 hover:text-red-300"
                  >
                    Log out
                  </button>
                </li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
