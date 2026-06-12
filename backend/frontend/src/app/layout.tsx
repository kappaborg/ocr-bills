import type { Metadata } from "next";
import localFont from "next/font/local";
import { Analytics } from "@vercel/analytics/react";
import "./globals.css";
import { AppBackground } from "@/components/AppBackground";
import { TopNav } from "@/components/TopNav";
import { ToastProvider } from "@/components/Toast";
import { ConfirmProvider } from "@/components/ConfirmDialog";
import { THEME_NOFLASH_SCRIPT, ThemeProvider } from "@/components/ThemeProvider";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ocr-bills.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "ExTaSy — Expense Tracking System",
    template: "%s · ExTaSy",
  },
  description:
    "Scan receipts in any language — Bosnian, Russian, Arabic, Japanese — and get perfectly parsed expenses. Multi-currency, budgets, recurring detection, bank reconciliation, accountant-ready exports.",
  keywords: [
    "receipt OCR", "expense tracking", "receipt scanner", "multi-currency",
    "budget tracker", "bank reconciliation", "expense reports",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "ExTaSy",
    title: "ExTaSy — Receipts you can actually read",
    description:
      "Snap a photo, get a perfectly parsed receipt — in any language. Budgets, recurring-expense detection, and accountant-ready exports built in.",
  },
  twitter: {
    card: "summary_large_image",
    title: "ExTaSy — Receipts you can actually read",
    description:
      "Receipt OCR in any language. Multi-currency tracking, budgets, bank reconciliation, one-click exports.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        {/* Set data-theme before React hydrates — eliminates the dark-to-light
            flash for users who chose light mode. Sourced from
            ThemeProvider so the key + logic stay in one place. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_NOFLASH_SCRIPT }} />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-[family-name:var(--font-geist-sans)]`}
      >
        {/* Skip-to-content link — keyboard users tab once to jump past the
            nav. Visually hidden until focused. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[100] focus:rounded-md focus:bg-cyan-500 focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-slate-950"
        >
          Skip to content
        </a>
        <ThemeProvider>
          <ToastProvider>
            <ConfirmProvider>
              <AppBackground>
                <TopNav />
                <div id="main-content">{children}</div>
              </AppBackground>
            </ConfirmProvider>
          </ToastProvider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  );
}
