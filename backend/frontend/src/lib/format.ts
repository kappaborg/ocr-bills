/** Format API ISO date strings for display (avoids raw ISO in UI). */
export function formatReceiptDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Humanized "time ago" label — "2 hours ago", "yesterday", "3 weeks ago".
 * Past dates only; future dates fall back to the absolute date.
 * Returns "—" for null/invalid inputs so callers can pass straight from API.
 */
export function formatTimeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);

  const seconds = (Date.now() - d.getTime()) / 1000;
  if (seconds < 0) return formatReceiptDate(iso);  // future → fall back to absolute
  if (seconds < 45) return "just now";
  if (seconds < 90) return "a minute ago";

  const minutes = seconds / 60;
  if (minutes < 45) return `${Math.round(minutes)} minutes ago`;
  if (minutes < 90) return "an hour ago";

  const hours = minutes / 60;
  if (hours < 22) return `${Math.round(hours)} hours ago`;
  if (hours < 36) return "yesterday";

  const days = hours / 24;
  if (days < 7) return `${Math.round(days)} days ago`;
  if (days < 10) return "a week ago";

  const weeks = days / 7;
  if (weeks < 5) return `${Math.round(weeks)} weeks ago`;

  const months = days / 30.44;
  if (months < 1.5) return "a month ago";
  if (months < 11) return `${Math.round(months)} months ago`;

  const years = days / 365.25;
  if (years < 1.5) return "a year ago";
  return `${Math.round(years)} years ago`;
}

// Map currency code → BCP-47 locale for best Intl.NumberFormat formatting
const _CURRENCY_LOCALE: Record<string, string> = {
  USD: "en-US", CAD: "en-CA", AUD: "en-AU", NZD: "en-NZ",
  GBP: "en-GB", EUR: "de-DE", CHF: "de-CH",
  JPY: "ja-JP", CNY: "zh-CN", HKD: "zh-HK", TWD: "zh-TW",
  KRW: "ko-KR",
  RUB: "ru-RU", UAH: "uk-UA",
  INR: "hi-IN", PKR: "ur-PK", BDT: "bn-BD",
  THB: "th-TH", IDR: "id-ID", MYR: "ms-MY", VND: "vi-VN",
  AED: "ar-AE", SAR: "ar-SA", QAR: "ar-QA", KWD: "ar-KW",
  ILS: "he-IL", TRY: "tr-TR",
  SEK: "sv-SE", NOK: "nb-NO", DKK: "da-DK",
  PLN: "pl-PL", CZK: "cs-CZ", HUF: "hu-HU", RON: "ro-RO",
  BGN: "bg-BG", RSD: "sr-RS", BAM: "bs-BA", HRK: "hr-HR",
  GEL: "ka-GE", AMD: "hy-AM", AZN: "az-AZ",
  NGN: "en-NG", ZAR: "en-ZA", KES: "sw-KE",
  BRL: "pt-BR", MXN: "es-MX", ARS: "es-AR",
};

/**
 * Format a monetary amount using the currency's native locale and symbol.
 * Falls back to "1,234.56 XYZ" format when currency is unknown.
 */
export function formatCurrency(
  amount: number | null | undefined,
  currency: string | null | undefined,
): string {
  if (amount == null) return "—";
  const cur = (currency || "").toUpperCase();
  if (!cur) return amount.toFixed(2);

  const locale = _CURRENCY_LOCALE[cur] ?? "en-US";
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: cur,
      minimumFractionDigits: cur === "JPY" || cur === "KRW" || cur === "VND" ? 0 : 2,
      maximumFractionDigits: cur === "KWD" || cur === "BHD" || cur === "OMR" ? 3 : cur === "JPY" || cur === "KRW" || cur === "VND" ? 0 : 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${cur}`;
  }
}

// ── FX rates ─────────────────────────────────────────────────────────────
// Base unit: 1 USD. The backend serves live rates at /fx/rates and falls back
// to this static table. We keep the table client-side too so first paint
// works before the API call resolves.
const _STATIC_USD_RATES: Record<string, number> = {
  USD: 1,
  EUR: 0.92,
  GBP: 0.79,
  CHF: 0.88,
  JPY: 156,
  CNY: 7.25,
  KRW: 1370,
  INR: 83.5,
  RUB: 92,
  TRY: 32.5,
  AED: 3.67,
  SAR: 3.75,
  QAR: 3.64,
  ILS: 3.7,
  BAM: 1.78,
  RSD: 108,
  HRK: 6.85,
  BGN: 1.78,
  PLN: 4.05,
  CZK: 23,
  HUF: 360,
  RON: 4.55,
  UAH: 41,
  GEL: 2.65,
  SEK: 10.5,
  NOK: 10.7,
  DKK: 6.85,
  CAD: 1.36,
  AUD: 1.52,
  NZD: 1.64,
  MXN: 17.2,
  BRL: 5.05,
  ARS: 1000,
  ZAR: 18.5,
  NGN: 1500,
  THB: 36,
  IDR: 16100,
  MYR: 4.7,
  VND: 25400,
  SGD: 1.34,
  HKD: 7.82,
  TWD: 32.3,
  PHP: 58,
};

// Live rates cache, populated by callers via setFxRates(); falls back to static.
let _liveRates: Record<string, number> | null = null;

export function setFxRates(rates: Record<string, number> | null) {
  _liveRates = rates && Object.keys(rates).length > 0 ? rates : null;
}

function _activeRates(): Record<string, number> {
  return _liveRates ?? _STATIC_USD_RATES;
}

/**
 * Convert `amount` from `fromCcy` into `toCcy` using cached FX rates (live
 * when available, static otherwise). Returns null if either currency is
 * unknown so callers can fall back to the native amount.
 */
export function convertCurrency(
  amount: number | null | undefined,
  fromCcy: string | null | undefined,
  toCcy: string | null | undefined,
): number | null {
  if (amount == null) return null;
  const from = (fromCcy || "").toUpperCase();
  const to = (toCcy || "").toUpperCase();
  if (!from || !to) return null;
  if (from === to) return amount;

  const rates = _activeRates();
  const fromRate = rates[from];
  const toRate = rates[to];
  if (fromRate == null || toRate == null) return null;
  return (amount / fromRate) * toRate;
}

/** Currencies offered in the dashboard selector. Order = display order. */
export const SUPPORTED_DISPLAY_CURRENCIES: string[] = [
  "BAM", "EUR", "USD", "GBP", "JPY", "CHF", "TRY", "RUB", "RSD", "AED", "SAR",
];
