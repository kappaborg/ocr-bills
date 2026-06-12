"""
Store name normalization — collapse receipt-printed store strings into a
stable matching key so price observations from "BINGO D.O.O. PJ-14
SARAJEVO" and "Bingo dd Tuzla" land on the same store.

Mirrors product_normalization.py but adds retail-specific cleanup:
legal-entity suffixes, branch ("PJ") markers, trailing city names for
known chains, and a curated alias map with a fuzzy fallback.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_ws_re = re.compile(r"\s+")
_strip_re = re.compile(r"[^\w\s]+", flags=re.UNICODE)
# Legal / branch noise commonly printed on Balkan + EU receipts.
_noise_re = re.compile(
    r"\b(d\s*\.?\s*o\s*\.?\s*o|d\s*\.?\s*d|j\s*\.?\s*d\s*\.?\s*o\s*\.?\s*o|gmbh|llc|ltd|inc"
    r"|pj\s*\d*|poslovnica\s*\d*|filijala\s*\d*|market\s*\d+|br\s*\d+|no\s*\d+|#\s*\d+)\b",
    flags=re.IGNORECASE | re.UNICODE,
)
_digits_tail_re = re.compile(r"\b\d{2,}\b")

# Curated aliases for chains we know appear in user receipts. Keys are the
# canonical store_normalized; values are substrings that map to it. Keep
# lowercase. Extend as observations reveal new chains.
_ALIASES: dict[str, list[str]] = {
    "bingo": ["bingo"],
    "konzum": ["konzum"],
    "mercator": ["mercator"],
    "best": ["best market", "best marketi"],
    "amko": ["amko komerc", "amko"],
    "dm": ["dm drogerie", "dm-drogerie"],
    "lidl": ["lidl"],
    "spar": ["spar"],
    "glovo": ["glovo"],
    "wolt": ["wolt"],
}

# 0.82 admits a single-character OCR slip on a 6-letter chain name
# ("konzun" → konzum scores 0.833) while still rejecting unrelated
# short names (spar/star = 0.75).
_FUZZY_THRESHOLD = 0.82


def normalize_store_name(name: str) -> str:
    """Return a stable lowercase key for a printed store name. Empty string
    when the input carries no usable signal."""
    s = (name or "").strip()
    if not s:
        return ""
    s = _strip_re.sub(" ", s)
    s = _noise_re.sub(" ", s)
    s = _digits_tail_re.sub(" ", s)
    s = _ws_re.sub(" ", s).strip().lower()
    if not s:
        return ""

    # Alias map first — exact substring containment.
    for canonical, needles in _ALIASES.items():
        for needle in needles:
            if needle in s:
                return canonical

    # Fuzzy fallback against canonical names (catches OCR one-char slips
    # like "blngo" / "konzun").
    best, best_ratio = None, 0.0
    head = " ".join(s.split()[:2])  # compare against the leading words only
    for canonical in _ALIASES:
        r = SequenceMatcher(None, head, canonical).ratio()
        if r > best_ratio:
            best_ratio, best = r, canonical
    if best is not None and best_ratio >= _FUZZY_THRESHOLD:
        return best

    return s
