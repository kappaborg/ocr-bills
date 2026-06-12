import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ocr-bills.vercel.app";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Authed app surface — nothing useful for crawlers, avoid wasting
        // crawl budget + leaking app URLs into search results.
        disallow: [
          "/dashboard", "/receipt/", "/inbox", "/inventory", "/need-to-buy",
          "/reconcile", "/settings", "/upload", "/scan", "/onboarding",
          "/billing/",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
