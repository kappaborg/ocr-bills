import re


_ws_re = re.compile(r"\s+")
# Keep digits, Unicode letters across all scripts (\w in Unicode covers Latin,
# Cyrillic, Arabic, CJK, Hangul, Devanagari, Greek, Hebrew, etc.).
_strip_re = re.compile(r"[^\w\s]+", flags=re.UNICODE)


def normalize_product_name(name: str) -> str:
    """
    Normalize a receipt item name into a stable matching key.

    Strips punctuation, folds whitespace, lowercases. Keeps letters from any
    script (Latin, Cyrillic, Arabic, CJK, Hangul, Thai, Devanagari, etc.) so
    products in non-Latin receipts don't all collapse to the empty string.
    """
    s = (name or "").strip()
    s = _strip_re.sub(" ", s)
    s = _ws_re.sub(" ", s).strip()
    return s.lower()

