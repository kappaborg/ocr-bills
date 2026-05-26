"""
Live foreign-exchange rates with a 24h in-memory cache.

Uses frankfurter.app — free, no API key, daily ECB-derived rates.
Falls back to a baked-in static table on network failure so the
frontend currency selector keeps working offline.
"""
from __future__ import annotations

import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException


router = APIRouter()


_BASE = "USD"
_CACHE: dict[str, object] = {"rates": None, "fetched_at": 0.0, "base": _BASE}
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h

# Frankfurter doesn't quote BAM (Bosnian convertible mark) but the BAM peg is
# fixed at 1 EUR = 1.95583 BAM, so we derive it once at fetch time.
_BAM_PER_EUR = 1.95583

# Static fallback (approximate, USD-base). Mirrors lib/format.ts so the front-
# end and back-end agree when the network is unavailable.
_STATIC_USD_RATES: dict[str, float] = {
    "USD": 1.0, "EUR": 0.92, "GBP": 0.79, "CHF": 0.88, "JPY": 156.0,
    "CNY": 7.25, "KRW": 1370.0, "INR": 83.5, "RUB": 92.0, "TRY": 32.5,
    "AED": 3.67, "SAR": 3.75, "QAR": 3.64, "ILS": 3.7, "BAM": 1.78,
    "RSD": 108.0, "HRK": 6.85, "BGN": 1.78, "PLN": 4.05, "CZK": 23.0,
    "HUF": 360.0, "RON": 4.55, "UAH": 41.0, "GEL": 2.65, "SEK": 10.5,
    "NOK": 10.7, "DKK": 6.85, "CAD": 1.36, "AUD": 1.52, "NZD": 1.64,
    "MXN": 17.2, "BRL": 5.05, "ARS": 1000.0, "ZAR": 18.5, "NGN": 1500.0,
    "THB": 36.0, "IDR": 16100.0, "MYR": 4.7, "VND": 25400.0, "SGD": 1.34,
    "HKD": 7.82, "TWD": 32.3, "PHP": 58.0,
}


def _is_fresh() -> bool:
    return _CACHE.get("rates") is not None and (time.time() - float(_CACHE["fetched_at"])) < _CACHE_TTL_SECONDS


def _derive_bam(rates: dict[str, float]) -> dict[str, float]:
    """frankfurter omits BAM — derive it from the locked EUR peg."""
    eur = rates.get("EUR")
    if eur:
        rates["BAM"] = eur * _BAM_PER_EUR
    return rates


def _fetch_live_rates() -> Optional[dict[str, float]]:
    try:
        with httpx.Client(timeout=4.0) as client:
            r = client.get(f"https://api.frankfurter.app/latest?from={_BASE}")
            r.raise_for_status()
            data = r.json()
        rates = data.get("rates") or {}
        rates[_BASE] = 1.0
        return _derive_bam(rates)
    except Exception:
        return None


@router.get("/rates")
def get_rates():
    """
    Returns base=USD rates: { "USD": 1, "EUR": 0.92, ... }
    Cached for 24h. Falls back to a static table on network failure.
    """
    if not _is_fresh():
        live = _fetch_live_rates()
        if live is not None:
            _CACHE["rates"] = live
            _CACHE["fetched_at"] = time.time()
            _CACHE["source"] = "frankfurter"
        elif _CACHE.get("rates") is None:
            _CACHE["rates"] = _derive_bam(dict(_STATIC_USD_RATES))
            _CACHE["fetched_at"] = time.time()
            _CACHE["source"] = "static-fallback"

    return {
        "base": _BASE,
        "rates": _CACHE["rates"],
        "fetched_at": _CACHE["fetched_at"],
        "source": _CACHE.get("source", "static-fallback"),
    }


@router.get("/convert")
def convert(amount: float, from_currency: str, to_currency: str):
    """Convenience server-side conversion. Returns null when currency unknown."""
    rates = get_rates()["rates"]
    f = (from_currency or "").upper()
    t = (to_currency or "").upper()
    if f not in rates or t not in rates:
        raise HTTPException(status_code=400, detail=f"Unknown currency: {f if f not in rates else t}")
    converted = (amount / rates[f]) * rates[t]
    return {"amount": amount, "from": f, "to": t, "converted": converted}
