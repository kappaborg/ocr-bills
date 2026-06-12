import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "ExTaSy — Receipts you can actually read";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Programmatic OG image — rendered by Next at /opengraph-image and
// referenced automatically from the metadata. Keeps branding in code so
// there's no PNG to forget to update.
export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          background: "linear-gradient(135deg, #020617 0%, #0f172a 60%, #042f2e 100%)",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 24,
          }}
        >
          <div
            style={{
              width: 88,
              height: 88,
              borderRadius: 24,
              background: "linear-gradient(135deg, #22d3ee, #34d399)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 48,
              color: "#020617",
              fontWeight: 700,
            }}
          >
            ◈
          </div>
          <div style={{ display: "flex", fontSize: 72, fontWeight: 700, color: "#f1f5f9" }}>
            Ex<span style={{ color: "#22d3ee" }}>TaSy</span>
          </div>
        </div>
        <div
          style={{
            marginTop: 36,
            fontSize: 40,
            color: "#e2e8f0",
            fontWeight: 600,
            textAlign: "center",
          }}
        >
          Receipts you can actually read.
        </div>
        <div
          style={{
            marginTop: 16,
            fontSize: 26,
            color: "#94a3b8",
            textAlign: "center",
            maxWidth: 860,
          }}
        >
          Receipt OCR in any language · Multi-currency · Budgets · Bank reconciliation
        </div>
        <div
          style={{
            marginTop: 40,
            fontSize: 20,
            color: "#22d3ee",
            padding: "12px 28px",
            borderRadius: 14,
            border: "1px solid rgba(34,211,238,0.4)",
            background: "rgba(34,211,238,0.08)",
          }}
        >
          Free for 20 receipts/month — no credit card
        </div>
      </div>
    ),
    { ...size },
  );
}
