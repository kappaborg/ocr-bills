import os
import re
from typing import Optional

from app.core.config import settings


def _count_cyrillic(s: str) -> int:
    return sum(1 for ch in (s or "") if "Ѐ" <= ch <= "ӿ")


def _count_latin(s: str) -> int:
    return sum(1 for ch in (s or "") if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))


def _apply_exif_rotation(img):
    try:
        from PIL import ImageOps
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def _cap_resolution(img, max_dim: int = 3500):
    try:
        w, h = img.size
        if max(w, h) <= max_dim:
            return img
        scale = max_dim / max(w, h)
        from PIL.Image import Resampling
        return img.resize((int(w * scale), int(h * scale)), resample=Resampling.LANCZOS)
    except Exception:
        return img


def _maybe_upscale(img):
    try:
        w, h = img.size
        if min(w, h) >= 1000:
            return None
        from PIL.Image import Resampling
        scale = max(2, -(-1000 // min(w, h)))
        return img.resize((w * scale, h * scale), resample=Resampling.LANCZOS)
    except Exception:
        return None


def _preprocess(img):
    try:
        from PIL import ImageEnhance, ImageFilter, ImageOps
        gray = img.convert("L")
        denoised = gray.filter(ImageFilter.MedianFilter(size=3))
        auto = ImageOps.autocontrast(denoised, cutoff=2)
        contrast = ImageEnhance.Contrast(auto).enhance(1.8)
        sharp = ImageEnhance.Sharpness(contrast).enhance(1.4)
        return sharp
    except Exception:
        return img


def _preprocess_strong(img):
    try:
        from PIL import ImageEnhance, ImageFilter, ImageOps
        gray = img.convert("L")
        denoised = gray.filter(ImageFilter.MedianFilter(size=3))
        auto = ImageOps.autocontrast(denoised, cutoff=5)
        contrast = ImageEnhance.Contrast(auto).enhance(2.5)
        sharp = ImageEnhance.Sharpness(contrast).enhance(1.6)
        return sharp.point(lambda p: 255 if p > 160 else p)
    except Exception:
        return img


def _preprocess_adaptive(img):
    try:
        from PIL import ImageChops, ImageFilter
        gray = img.convert("L")
        w, h = gray.size
        radius = min(40, max(15, min(w, h) // 40))
        bg = gray.filter(ImageFilter.GaussianBlur(radius=radius))
        diff = ImageChops.subtract(bg, gray, scale=1, offset=128)
        return diff.point(lambda p: 0 if p > 135 else 255)
    except Exception:
        return img


def _score_ocr_text(s: str) -> int:
    su = (s or "").upper()
    keyword_hits = sum(
        1
        for kw in ["UKUPNO", "UPLACENO", "UPLATENO", "TOTAL", "TOIAL", "GOTOVINA",
                   "ИТОГО", "ВСЕГО", "СУММА"]
        if kw in su
    )
    money_decimal_hits = len(re.findall(r"\d[\d\s]*[.,]\d{1,3}", s or ""))
    alpha_hits = sum(ch.isalpha() for ch in s or "")
    cyr = _count_cyrillic(s)
    lat = _count_latin(s)
    script_bonus = cyr * 3 + lat
    return keyword_hits * 100 + money_decimal_hits * 10 + alpha_hits + script_bonus


def _ocr_image(img, lang: str, cfg: str) -> tuple[str, int]:
    """Run a single Tesseract call and return (text, score)."""
    import pytesseract
    try:
        t = pytesseract.image_to_string(img, lang=lang, config=cfg)
        return t, _score_ocr_text(t)
    except Exception:
        return "", -1


def extract_text_from_image(file_path: str) -> str:
    """
    OCR adapter using a fast tiered strategy.

    Tier 1: primary lang + best PSM + standard preprocessing (1 call)
    Tier 2: primary lang × 2 PSMs × 2 preprocessing variants (4 calls)
    Tier 3: fallback "eng" × 2 PSMs × 2 preprocessing variants (4 calls)

    Maximum ~9 Tesseract calls instead of the previous 168-call brute force.
    Early exit as soon as a high-confidence result is found (score >= 150).
    """
    if settings.GOOGLE_VISION_API_KEY:
        raise RuntimeError("Google Vision OCR is not configured in this MVP scaffold.")

    try:
        import pytesseract
        from PIL import Image
    except Exception as e:
        raise RuntimeError("Local OCR is not available (missing pytesseract/Pillow).") from e

    if not os.path.exists(file_path):
        raise RuntimeError("Uploaded file not found on disk.")

    try:
        img = Image.open(file_path)

        # Fix phone camera orientation before anything else
        img = _apply_exif_rotation(img)

        # Downscale huge images — no accuracy benefit past ~3500px
        img = _cap_resolution(img)

        # Upscale only if image is genuinely small (screenshots, thumbnails)
        up = _maybe_upscale(img)
        work = up if up is not None else img

        # Build preprocessing variants
        pre = _preprocess(work)
        pre_adaptive = _preprocess_adaptive(work)

        # Primary language string from config
        primary_lang = settings.TESSERACT_LANGS or "eng+rus"

        # The two most reliable PSM modes for receipts:
        #   PSM 6 = uniform block (best for clean, straight receipts)
        #   PSM 4 = single column (best for narrow/curved receipts)
        PSM6 = "--oem 1 --psm 6 -c preserve_interword_spaces=1"
        PSM4 = "--oem 1 --psm 4 -c preserve_interword_spaces=1"
        PSM11 = "--oem 1 --psm 11 -c preserve_interword_spaces=1"

        best_text = ""
        best_score = -1

        def _update(text: str, score: int) -> None:
            nonlocal best_text, best_score
            if score > best_score and (text or "").strip():
                best_score = score
                best_text = text

        # ── Tier 1: quick single call with primary lang + PSM6 + standard preprocess ──
        t, sc = _ocr_image(pre, primary_lang, PSM6)
        _update(t, sc)
        if best_score >= 150:
            return best_text

        # ── Tier 2: primary lang × {PSM4, PSM11} × {standard, adaptive} ──
        for cfg in (PSM4, PSM11):
            for variant in (pre, pre_adaptive):
                t, sc = _ocr_image(variant, primary_lang, cfg)
                _update(t, sc)
                if best_score >= 150:
                    return best_text

        # Also try PSM6 + adaptive for uneven lighting
        t, sc = _ocr_image(pre_adaptive, primary_lang, PSM6)
        _update(t, sc)
        if best_score >= 100:
            return best_text

        # ── Tier 3: fallback to "eng" and "rus" individually if primary is combined ──
        fallback_langs = []
        if "+" in primary_lang:
            fallback_langs = ["eng", "rus"]
        elif primary_lang != "eng":
            fallback_langs = ["eng"]

        for lang in fallback_langs:
            for cfg in (PSM6, PSM4):
                for variant in (pre, pre_adaptive):
                    t, sc = _ocr_image(variant, lang, cfg)
                    _update(t, sc)
                    if best_score >= 100:
                        return best_text

        if not (best_text or "").strip():
            raise RuntimeError("OCR produced empty output.")
        return best_text

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError("OCR runtime error.") from e
