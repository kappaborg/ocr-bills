from typing import Optional

from langdetect import detect, LangDetectException


def detect_language(text: str) -> Optional[str]:
    raw = text or ""
    cyr = sum(1 for ch in raw if "Ѐ" <= ch <= "ӿ")
    lat = sum(1 for ch in raw if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
    total_alpha = cyr + lat

    # Strongly Cyrillic dominant — return ex-YU locale (safe default for target use-case).
    if cyr >= 20 and cyr >= lat:
        return "sr"

    # Weakly Cyrillic — any meaningful Cyrillic presence on a mixed-script receipt.
    # Phone photos of Bosnian/Serbian receipts often have Latin menus + Cyrillic headers.
    if cyr >= 4 and total_alpha > 0 and (cyr / total_alpha) >= 0.12:
        return "sr"

    cleaned = raw.strip()
    if len(cleaned) < 20:
        return None

    cleaned = cleaned.replace(" ", " ").replace(" ", " ")
    cleaned = "".join(ch for ch in cleaned if ch.isalpha() or ch.isspace())
    cleaned = cleaned.strip()
    if len(cleaned) < 10:
        return None

    try:
        guessed = detect(cleaned)
        # When any Cyrillic is present, reject obviously wrong guesses from langdetect.
        if cyr >= 10:
            supported = {
                "bs", "hr", "sr", "ru", "uk", "bg", "mk", "be", "kk",
                "az", "en", "tr", "de", "fr", "es", "it", "nl", "pt",
            }
            if guessed not in supported:
                return "sr"
        return guessed
    except LangDetectException:
        return None
