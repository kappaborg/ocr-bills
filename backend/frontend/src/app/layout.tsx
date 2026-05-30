import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { AppBackground } from "@/components/AppBackground";
import { TopNav } from "@/components/TopNav";
import { ToastProvider } from "@/components/Toast";
import { ConfirmProvider } from "@/components/ConfirmDialog";

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

export const metadata: Metadata = {
  title: "ExTaSy — Expense Tracking System",
  description: "Receipt OCR, multi-currency tracking, budgets, and spending insights",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
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
        <ToastProvider>
          <ConfirmProvider>
            <AppBackground>
              <TopNav />
              <div id="main-content">{children}</div>
            </AppBackground>
          </ConfirmProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
