import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { AppBackground } from "@/components/AppBackground";
import { TopNav } from "@/components/TopNav";

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
  title: "FluxReceipt — Smart receipt scan",
  description: "Receipt OCR + spending insights",
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
        <AppBackground>
          <TopNav />
          {children}
        </AppBackground>
      </body>
    </html>
  );
}
