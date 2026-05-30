"use client";

// Tiny lazy-loading receipt thumbnail.
//
// Why a dedicated component instead of just <img src="…">?
//   - Authenticated image fetch: the backend requires Authorization header,
//     which <img src> can't send. We grab the blob via fetch and stick it
//     in an object URL.
//   - Per-session memoization: navigating between Inbox and Dashboard
//     shouldn't re-download the same thumbnail.
//   - Graceful fallback: shows a tinted placeholder while loading and a
//     receipt-icon when the image isn't available (deleted, missing, etc.).

import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// Module-level cache shared across all <ReceiptThumbnail> instances in this
// browser tab. Keys are receipt IDs. Values are object URLs.
const _thumbUrlCache = new Map<number, string>();
const _thumbInflight = new Map<number, Promise<string | null>>();

async function fetchThumb(receiptId: number, token: string): Promise<string | null> {
  const cached = _thumbUrlCache.get(receiptId);
  if (cached) return cached;

  const pending = _thumbInflight.get(receiptId);
  if (pending) return pending;

  const promise = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/receipts/${receiptId}/thumbnail`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      _thumbUrlCache.set(receiptId, url);
      return url;
    } catch {
      return null;
    } finally {
      _thumbInflight.delete(receiptId);
    }
  })();

  _thumbInflight.set(receiptId, promise);
  return promise;
}

export function ReceiptThumbnail({
  receiptId,
  token,
  alt,
  size = 40,
  rounded = "rounded-lg",
}: {
  receiptId: number;
  token: string | null;
  alt: string;
  size?: number;
  rounded?: string;
}) {
  const [url, setUrl] = useState<string | null>(() => _thumbUrlCache.get(receiptId) ?? null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!token || url) return;
    let alive = true;
    fetchThumb(receiptId, token).then((u) => {
      if (!alive) return;
      if (u) setUrl(u);
      else setFailed(true);
    });
    return () => { alive = false; };
  }, [receiptId, token, url]);

  const sizeClass = `${rounded} flex shrink-0 items-center justify-center overflow-hidden bg-white/5 ring-1 ring-white/10`;
  const sizeStyle = { width: size, height: size };

  if (url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={alt}
        loading="lazy"
        decoding="async"
        style={sizeStyle}
        className={`object-cover ${rounded} ring-1 ring-white/10`}
      />
    );
  }

  // Loading or failed — show a tinted placeholder with a small receipt glyph.
  return (
    <div className={sizeClass} style={sizeStyle} aria-label={failed ? "No thumbnail" : "Loading thumbnail"}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5 text-slate-600">
        <path strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
          d="M5 3.5h14v17l-3-2-3 2-3-2-3 2-2-2V3.5z M8.5 8h7 M8.5 11.5h7 M8.5 15h4" />
      </svg>
    </div>
  );
}
