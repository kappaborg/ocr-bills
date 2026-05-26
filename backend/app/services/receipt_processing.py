import os

from app.core.config import settings
from app.db.models import Receipt, ReceiptItem, Category, ReceiptStatus
from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.services.categorization import categorize_item
from app.services.language_detection import detect_language
from app.services.ocr import run_ocr
from app.services.receipt_parser import extract_tax_amount, looks_like_bosnia_fiscal_receipt, parse_receipt


def process_receipt(receipt_id: int) -> None:
    db = SessionLocal()
    try:
        init_db(db)

        receipt: Receipt | None = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            return

        # Guard: if the user already confirmed this receipt (race with live-preview or fast confirm),
        # do not overwrite their data.
        if receipt.processing_status == ReceiptStatus.confirmed.value:
            return

        receipt.processing_status = ReceiptStatus.processing.value
        receipt.processing_error = None
        db.commit()

        file_path = os.path.join(settings.UPLOAD_DIR, receipt.storage_key)
        ocr_result = run_ocr(file_path)
        raw_text = ocr_result.raw_text

        # When the engine already extracted structured fields (VLM path), trust
        # them: skip the regex parser entirely. The VLM understands receipt
        # context better than any regex can.
        vlm_struct = ocr_result.structured

        lang = (vlm_struct.detected_language if vlm_struct and vlm_struct.detected_language
                else detect_language(raw_text))
        parsed = parse_receipt(raw_text) if vlm_struct is None else None

        # When the VLM gave us currency, skip the inference dance.
        vlm_currency = vlm_struct.currency if vlm_struct else None
        parsed_currency = parsed.currency if parsed else vlm_currency

        # Lightweight currency inference (only when OCR text didn't contain a clear symbol/code).
        inferred_currency = None
        if parsed_currency is None:
            if looks_like_bosnia_fiscal_receipt(raw_text):
                inferred_currency = "BAM"

        # Cyrillic-script fallback: even when langdetect says 'en', Cyrillic chars
        # strongly suggest an ex-YU receipt (target locale = BAM).
        if parsed_currency is None and inferred_currency is None:
            cyr_count = sum(1 for ch in raw_text if "Ѐ" <= ch <= "ӿ")
            if cyr_count >= 10:
                inferred_currency = "BAM"

        if parsed_currency is None and inferred_currency is None and lang:
            lang_prefix = lang.split("-")[0].lower()
            _LANG_CURRENCY: dict[str, str] = {
                # South Slavic / Balkan
                "bs": "BAM", "sr": "RSD", "hr": "EUR", "mk": "MKD", "sq": "ALL",
                "bg": "BGN", "sl": "EUR",
                # Western European
                "fr": "EUR", "de": "EUR", "es": "EUR", "it": "EUR",
                "nl": "EUR", "pt": "EUR", "el": "EUR", "fi": "EUR",
                # Nordic
                "sv": "SEK", "no": "NOK", "nb": "NOK", "nn": "NOK", "da": "DKK",
                # Eastern European
                "pl": "PLN", "cs": "CZK", "sk": "EUR", "hu": "HUF",
                "ro": "RON", "uk": "UAH", "be": "BYN", "lt": "EUR", "lv": "EUR",
                "et": "EUR",
                # Caucasus / Central Asia
                "ka": "GEL", "hy": "AMD", "az": "AZN",
                "kk": "KZT", "uz": "UZS", "ky": "KGS", "tg": "TJS", "tk": "TMT",
                # Slavic / Russian
                "ru": "RUB",
                # Middle East
                "ar": "AED",  # generic Arabic → AED (UAE); SAR/QAR etc. caught by symbol detection
                "he": "ILS", "fa": "IRR", "tr": "TRY",
                # South / Southeast Asia
                "hi": "INR", "bn": "BDT", "ur": "PKR", "ne": "NPR", "si": "LKR",
                "th": "THB", "vi": "VND", "id": "IDR", "ms": "MYR",
                "km": "KHR", "my": "MMK", "lo": "LAK",
                # East Asia
                "zh": "CNY", "ja": "JPY", "ko": "KRW",
                # African
                "sw": "KES", "am": "ETB",
                # English / other
                "en": "USD",
            }
            inferred_currency = _LANG_CURRENCY.get(lang_prefix)

        # Re-fetch to check if user confirmed while we were processing (race guard).
        db.refresh(receipt)
        if receipt.processing_status == ReceiptStatus.confirmed.value:
            return

        receipt.raw_text = raw_text[:200_000]  # keep MVP size bounded
        receipt.detected_language = lang or (parsed.detected_language if parsed else None)
        receipt.receipt_date = vlm_struct.receipt_date if vlm_struct else parsed.receipt_date
        receipt.store_name = vlm_struct.store_name if vlm_struct else parsed.store_name
        receipt.total_amount = vlm_struct.total_amount if vlm_struct else parsed.total_amount
        receipt.currency = parsed_currency or inferred_currency
        # VLM tax_amount is preferred; fall back to regex parsing of raw_text.
        receipt.tax_amount = (vlm_struct.tax_amount if vlm_struct and vlm_struct.tax_amount is not None
                              else extract_tax_amount(raw_text))
        receipt.processing_status = ReceiptStatus.parsed.value
        receipt.processing_error = None

        # Replace parsed items.
        receipt.items.clear()
        db.flush()

        categories = db.query(Category).filter(Category.user_id.is_(None)).all()
        categories_by_name = {c.name: c.id for c in categories}

        items_to_insert = vlm_struct.items if vlm_struct else (parsed.items if parsed else [])
        for it in items_to_insert:
            category_id, confidence = categorize_item(it.item_name, categories_by_name=categories_by_name)
            item = ReceiptItem(
                item_name=it.item_name,
                quantity=it.quantity,
                unit_price=it.unit_price,
                item_price=it.item_price,
                category_id=category_id,
                confidence_score=getattr(it, "confidence_score", ocr_result.confidence) if confidence is None else confidence,
            )
            receipt.items.append(item)

        db.add(receipt)
        db.commit()
    except Exception as e:
        try:
            receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
            if receipt and receipt.processing_status != ReceiptStatus.confirmed.value:
                receipt.processing_status = ReceiptStatus.error.value
                receipt.processing_error = str(e)[:2000]
                db.commit()
        finally:
            pass
    finally:
        db.close()

