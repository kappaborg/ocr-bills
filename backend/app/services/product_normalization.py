import re


_ws_re = re.compile(r"\s+")
_keep_re = re.compile(r"[^0-9a-zA-Z\u0400-\u04FF\u0100-\u017F\s]+", flags=re.UNICODE)


def normalize_product_name(name: str) -> str:
    """
    Normalize a receipt item name into a stable matching key.

    Keeps Latin + Cyrillic letters and digits, removes punctuation, folds whitespace,
    and lowercases.
    """
    s = (name or "").strip()
    s = _keep_re.sub(" ", s)
    s = _ws_re.sub(" ", s).strip()
    return s.lower()

