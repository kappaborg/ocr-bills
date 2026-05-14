import os

from app.core.config import settings
from app.db.models import Receipt, ReceiptItem, Category, ReceiptStatus
from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.services.categorization import categorize_item
from app.services.language_detection import detect_language
from app.services.ocr import extract_text_from_image
from app.services.receipt_parser import looks_like_bosnia_fiscal_receipt, parse_receipt


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
        raw_text = extract_text_from_image(file_path)

        lang = detect_language(raw_text)
        parsed = parse_receipt(raw_text)

        # Lightweight currency inference (only when OCR text didn't contain a clear symbol/code).
        inferred_currency = None
        if parsed.currency is None:
            if looks_like_bosnia_fiscal_receipt(raw_text):
                inferred_currency = "BAM"

        # Cyrillic-script fallback: even when langdetect says 'en', Cyrillic chars
        # strongly suggest an ex-YU receipt (target locale = BAM).
        if parsed.currency is None and inferred_currency is None:
            cyr_count = sum(1 for ch in raw_text if "Ѐ" <= ch <= "ӿ")
            if cyr_count >= 10:
                inferred_currency = "BAM"

        if parsed.currency is None and inferred_currency is None and lang:
            lang_prefix = lang.split("-")[0].lower()
            if lang_prefix in {"bs", "sr", "hr"}:
                inferred_currency = "BAM"
            elif lang_prefix in {"fr", "de", "es", "it", "nl", "pt"}:
                inferred_currency = "EUR"
            elif lang_prefix in {"tr"}:
                inferred_currency = "TRY"
            elif lang_prefix in {"ja"}:
                inferred_currency = "JPY"
            elif lang_prefix in {"ru", "uk", "be"}:
                inferred_currency = "RUB"
            elif lang_prefix in {"ko"}:
                inferred_currency = "KRW"
            elif lang_prefix in {"hi", "in"}:
                inferred_currency = "INR"
            elif lang_prefix in {"en"}:
                inferred_currency = "USD"

        # Re-fetch to check if user confirmed while we were processing (race guard).
        db.refresh(receipt)
        if receipt.processing_status == ReceiptStatus.confirmed.value:
            return

        receipt.raw_text = raw_text[:200_000]  # keep MVP size bounded
        receipt.detected_language = lang or parsed.detected_language
        receipt.receipt_date = parsed.receipt_date
        receipt.store_name = parsed.store_name
        receipt.total_amount = parsed.total_amount
        receipt.currency = parsed.currency or inferred_currency
        receipt.processing_status = ReceiptStatus.parsed.value
        receipt.processing_error = None

        # Replace parsed items.
        receipt.items.clear()
        db.flush()

        categories = db.query(Category).filter(Category.user_id.is_(None)).all()
        categories_by_name = {c.name: c.id for c in categories}

        for it in parsed.items:
            category_id, confidence = categorize_item(it.item_name, categories_by_name=categories_by_name)
            item = ReceiptItem(
                item_name=it.item_name,
                quantity=it.quantity,
                unit_price=it.unit_price,
                item_price=it.item_price,
                category_id=category_id,
                confidence_score=it.confidence_score if confidence is None else confidence,
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

