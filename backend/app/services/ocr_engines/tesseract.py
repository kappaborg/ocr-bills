"""
Tesseract engine — the existing pytesseract pipeline, lifted from app/services/ocr.py
verbatim. Returns raw text only; structured field extraction is handled downstream
by the regex parser.
"""
from __future__ import annotations

import os
import re

from app.core.config import settings
from app.services.ocr_engines.base import OCREngine, OCRResult


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
        for kw in [
            "UKUPNO", "UPLACENO", "UPLATENO", "TOTAL", "TOIAL", "GOTOVINA",
            "ИТОГО", "ВСЕГО", "СУММА", "РАЗОМ", "ВСЬОГО",
            "GESAMT", "SUMME", "BETRAG",
            "MONTANT", "PAYER",
            "TOPLAM", "TUTAR",
            "合計", "총액", "المجموع",
        ]
        if kw in su
    )
    money_decimal_hits = len(re.findall(r"\d[\d\s]*[.,]\d{1,3}", s or ""))
    alpha_hits = sum(ch.isalpha() for ch in s or "")
    cyr = _count_cyrillic(s)
    lat = _count_latin(s)
    return keyword_hits * 100 + money_decimal_hits * 10 + alpha_hits + (cyr * 3 + lat)


def _detect_script(img) -> str:
    try:
        import pytesseract
        data = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT, config="--psm 0")
        return data.get("script", "Latin") or "Latin"
    except Exception:
        return "Latin"


def _lang_packs_for_script(script: str) -> list[str]:
    mapping: dict[str, list[str]] = {
        "Latin":       [settings.TESSERACT_LANGS or "eng", "eng"],
        "Cyrillic":    [settings.TESSERACT_LANGS or "rus+srp+ukr+bul", "rus", "eng+rus"],
        "Arabic":      ["ara+eng", "ara"],
        "HanS":        ["chi_sim+eng", "chi_sim"],
        "HanT":        ["chi_tra+eng", "chi_tra", "chi_sim+eng"],
        "Japanese":    ["jpn+jpn_vert+eng", "jpn", "jpn_vert"],
        "Hangul":      ["kor+eng", "kor", "kor_vert"],
        "Devanagari":  ["hin+eng", "hin"],
        "Thai":        ["tha+eng", "tha"],
        "Hebrew":      ["heb+eng", "heb"],
        "Greek":       ["ell+eng", "ell"],
        "Georgian":    ["kat+eng", "kat"],
        "Armenian":    ["hye+eng", "hye"],
        "Bengali":     ["ben+eng", "ben"],
        "Tamil":       ["tam+eng", "tam"],
        "Telugu":      ["tel+eng", "tel"],
        "Kannada":     ["kan+eng", "kan"],
        "Malayalam":   ["mal+eng", "mal"],
        "Sinhala":     ["sin+eng", "sin"],
        "Myanmar":     ["mya+eng", "mya"],
        "Khmer":       ["khm+eng", "khm"],
        "Lao":         ["lao+eng", "lao"],
        "Tibetan":     ["bod+eng", "bod"],
        "Gujarati":    ["guj+eng", "guj"],
        "Gurmukhi":    ["pan+eng", "pan"],
        "Vietnamese":  ["vie+eng", "vie"],
    }
    return mapping.get(script, mapping["Latin"])


def _ocr_image(img, lang: str, cfg: str) -> tuple[str, int]:
    import pytesseract
    try:
        t = pytesseract.image_to_string(img, lang=lang, config=cfg)
        return t, _score_ocr_text(t)
    except Exception:
        return "", -1


class TesseractEngine(OCREngine):
    name = "tesseract"

    def extract(self, file_path: str, context=None) -> OCRResult:
        # Tesseract is regex-based; we can't usefully consume user context here.
        _ = context  # noqa: F841
        try:
            import pytesseract  # noqa: F401  (verify installed)
            from PIL import Image
        except Exception as e:
            raise RuntimeError("Local OCR is not available (missing pytesseract/Pillow).") from e

        if not os.path.exists(file_path):
            raise RuntimeError("Uploaded file not found on disk.")

        try:
            with Image.open(file_path) as _f:
                _f.load()
                img = _f.copy()

            img = _apply_exif_rotation(img)
            img = _cap_resolution(img)

            up = _maybe_upscale(img)
            work = up if up is not None else img

            script = _detect_script(work)
            pre = _preprocess(work)
            pre_adaptive = _preprocess_adaptive(work)

            lang_candidates = _lang_packs_for_script(script)
            primary_lang = lang_candidates[0]
            fallback_langs = lang_candidates[1:]

            if script in ("Japanese", "HanS", "HanT"):
                PSM6 = "--oem 1 --psm 5 -c preserve_interword_spaces=1"
                PSM4 = "--oem 1 --psm 6 -c preserve_interword_spaces=1"
                PSM11 = "--oem 1 --psm 4 -c preserve_interword_spaces=1"
            elif script in ("Arabic", "Hebrew"):
                PSM6 = "--oem 1 --psm 6 -c preserve_interword_spaces=1"
                PSM4 = "--oem 1 --psm 3 -c preserve_interword_spaces=1"
                PSM11 = "--oem 1 --psm 11 -c preserve_interword_spaces=1"
            else:
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

            t, sc = _ocr_image(pre, primary_lang, PSM6)
            _update(t, sc)
            if best_score >= 150:
                return OCRResult(raw_text=best_text, confidence=0.85, engine=self.name)

            for cfg in (PSM4, PSM11):
                for variant in (pre, pre_adaptive):
                    t, sc = _ocr_image(variant, primary_lang, cfg)
                    _update(t, sc)
                    if best_score >= 150:
                        return OCRResult(raw_text=best_text, confidence=0.8, engine=self.name)

            t, sc = _ocr_image(pre_adaptive, primary_lang, PSM6)
            _update(t, sc)
            if best_score >= 100:
                return OCRResult(raw_text=best_text, confidence=0.7, engine=self.name)

            for lang in fallback_langs[:2]:
                for cfg in (PSM6, PSM4):
                    for variant in (pre, pre_adaptive):
                        t, sc = _ocr_image(variant, lang, cfg)
                        _update(t, sc)
                        if best_score >= 100:
                            return OCRResult(raw_text=best_text, confidence=0.6, engine=self.name)

            if not (best_text or "").strip():
                raise RuntimeError("OCR produced empty output.")

            # Normalize confidence based on final score (rough heuristic).
            conf = min(0.6, max(0.2, best_score / 250))
            return OCRResult(raw_text=best_text, confidence=conf, engine=self.name)

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError("OCR runtime error.") from e
