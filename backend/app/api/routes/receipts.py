import os
import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.init_db import init_db
from app.db.models import Category, Receipt, ReceiptItem, ReceiptStatus
from app.schemas.receipts import (
    ReceiptConfirmRequest,
    ReceiptOut,
    ReceiptUploadResult,
    ReceiptUploadResponse,
)
from app.services.language_detection import detect_language
from app.services.ocr import extract_text_from_image
from app.services.receipt_parser import parse_receipt
from app.services.receipt_processing import process_receipt
from app.services.rate_limit import live_ocr_limiter


router = APIRouter()

ALLOWED_EXTS = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8MB per file (phone-friendly)

# Keywords that must never appear as item names (totals, tax lines, fiscal IDs).
_JUNK_KEYWORDS = {
    "UKUPNO", "UPLACENO", "UPLATENO", "GOTOVINA", "POVRAT",
    "TOTAL", "TOIAL", "CHANGE", "CASH", "CARD", "AMOUNT",
    "JIB", "PIB", "IBF", "PDV", "VAT", "OSN", "POV",
    "FISKAL", "RACUN", "RAČUN",
}


def _is_junk_item(item_name: str, item_price: float) -> bool:
    """Return True for OCR artifacts that should never be saved as receipt items."""
    name = (item_name or "").strip()
    name_upper = name.upper()

    if sum(ch.isalpha() for ch in name) < 2:
        return True
    if item_price <= 0 or item_price > 100_000:
        return True
    if any(kw in name_upper for kw in _JUNK_KEYWORDS):
        return True
    # Fiscal ID pattern: "JIB: A2B0S04"
    if re.search(r"\b(JIB|PIB|IBF|PDV|VAT)\s*[:=]", name, flags=re.IGNORECASE):
        return True
    # Looks like a date (e.g. "18.03.2026,")
    from app.services.receipt_parser import detect_receipt_date
    if detect_receipt_date(name) is not None:
        return True

    return False


def _storage_path(storage_key: str) -> str:
    return os.path.join(settings.UPLOAD_DIR, storage_key)


def _get_receipt_out(receipt: Receipt) -> ReceiptOut:
    items_out = []
    for it in receipt.items:
        items_out.append(
            {
                "id": it.id,
                "item_name": it.item_name,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "item_price": it.item_price,
                "category_id": it.category_id,
                "category_name": it.category.name if it.category else None,
                "confidence_score": it.confidence_score,
            }
        )

    return ReceiptOut(
        id=receipt.id,
        processing_status=receipt.processing_status,
        processing_error=receipt.processing_error,
        raw_text=receipt.raw_text,
        detected_language=receipt.detected_language,
        receipt_date=receipt.receipt_date,
        store_name=receipt.store_name,
        total_amount=receipt.total_amount,
        currency=receipt.currency,
        items=items_out,
    )


def _build_preview_out(raw_text: str, db: Session) -> ReceiptOut:
    """
    Build a transient ReceiptOut for live preview without persisting a Receipt row.
    """
    lang = detect_language(raw_text)
    parsed = parse_receipt(raw_text)

    # Map global categories by name for categorization.
    categories = db.query(Category).filter(Category.user_id.is_(None)).all()
    categories_by_name = {c.name: c.id for c in categories}

    # Reuse the same categorization logic as the async pipeline where possible.
    from app.services.categorization import categorize_item

    items_out: list[dict] = []
    for idx, it in enumerate(parsed.items):
        category_id, confidence = categorize_item(it.item_name, categories_by_name=categories_by_name)
        cat_name = None
        if category_id is not None:
            for c in categories:
                if c.id == category_id:
                    cat_name = c.name
                    break
        items_out.append(
            {
                "id": idx + 1,
                "item_name": it.item_name,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "item_price": it.item_price,
                "category_id": category_id,
                "category_name": cat_name,
                "confidence_score": it.confidence_score if confidence is None else confidence,
            }
        )

    return ReceiptOut(
        id=0,
        processing_status=ReceiptStatus.parsed.value,
        processing_error=None,
        raw_text=raw_text[:200_000],
        detected_language=lang or parsed.detected_language,
        receipt_date=parsed.receipt_date,
        store_name=parsed.store_name,
        total_amount=parsed.total_amount,
        currency=parsed.currency,
        items=items_out,
    )


@router.post("/upload", response_model=ReceiptUploadResponse)
def upload_receipts(
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    init_db(db)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results: list[dict] = []
    for uf in files:
        if uf.size is not None and uf.size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        ext = os.path.splitext(uf.filename or "")[1].lower()
        if ext not in ALLOWED_EXTS:
            # MVP limitation: OCR adapter currently supports raster images only.
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: jpg, jpeg, png.",
            )

        receipt_code = uuid.uuid4().hex
        storage_key = f"{user.id}/{receipt_code}/{uf.filename}"

        receipt = Receipt(
            user_id=user.id,
            storage_key=storage_key,
            processing_status=ReceiptStatus.queued.value,
        )
        db.add(receipt)
        db.commit()
        db.refresh(receipt)

        target_path = _storage_path(receipt.storage_key)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        with open(target_path, "wb") as f:
            content = uf.file.read()
            f.write(content)

        if background_tasks is not None:
            background_tasks.add_task(process_receipt, receipt.id)

        results.append({"receipt_id": receipt.id, "processing_status": receipt.processing_status})

    return {"results": results}


@router.post("/live-preview", response_model=ReceiptOut)
def live_preview_receipt(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Lightweight, synchronous OCR endpoint for live phone scanning.

    Does NOT persist a Receipt row — returns a transient preview so the
    client can overlay parsed content while the user is scanning.
    """
    init_db(db)

    # Basic rate limiting (single-process). Keeps the server safe when scanning live.
    ip = request.client.host if request.client else "unknown"
    if not live_ocr_limiter.allow(
        f"live-preview:{user.id}:{ip}",
        capacity=12,
        refill_per_sec=12 / 10.0,  # ~12 requests per 10 seconds
    ):
        raise HTTPException(status_code=429, detail="Too many requests")

    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: jpg, jpeg, png.",
        )

    # Store into a short‑lived temp location under the existing upload dir.
    preview_code = uuid.uuid4().hex
    storage_key = f"{user.id}/_preview/{preview_code}{ext}"
    target_path = _storage_path(storage_key)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    with open(target_path, "wb") as f:
        content = file.file.read()
        f.write(content)

    try:
        raw_text = extract_text_from_image(target_path)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"OCR could not read text from this image. Try better lighting or hold the camera steadier. ({exc})",
        )
    finally:
        # Clean up the temp preview file regardless of OCR outcome.
        try:
            os.remove(target_path)
        except OSError:
            pass

    if not (raw_text or "").strip():
        raise HTTPException(
            status_code=422,
            detail="OCR produced empty output. Try better lighting or a clearer angle.",
        )

    return _build_preview_out(raw_text, db)


@router.post("/from-frame", response_model=ReceiptUploadResult)
def create_receipt_from_frame(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Persist a single camera frame as a Receipt and enqueue normal processing.
    """
    init_db(db)

    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: jpg, jpeg, png.",
        )

    receipt_code = uuid.uuid4().hex
    storage_key = f"{user.id}/{receipt_code}/scan{ext}"

    receipt = Receipt(
        user_id=user.id,
        storage_key=storage_key,
        processing_status=ReceiptStatus.queued.value,
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    target_path = _storage_path(receipt.storage_key)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    with open(target_path, "wb") as f:
        f.write(file.file.read())

    if background_tasks is not None:
        background_tasks.add_task(process_receipt, receipt.id)

    return {"receipt_id": receipt.id, "processing_status": receipt.processing_status}


@router.get("", response_model=list[ReceiptUploadResult])
def list_receipts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # MVP: return minimal list.
    init_db(db)
    receipts = db.query(Receipt).filter(Receipt.user_id == user.id).order_by(Receipt.id.desc()).limit(50).all()
    return [
        {"receipt_id": r.id, "processing_status": r.processing_status}
        for r in receipts
    ]


@router.get("/{receipt_id}", response_model=ReceiptOut)
def get_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    init_db(db)
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id, Receipt.user_id == user.id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return _get_receipt_out(receipt)


@router.patch("/{receipt_id}/confirm", response_model=ReceiptOut)
def confirm_receipt(
    receipt_id: int,
    payload: ReceiptConfirmRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    init_db(db)
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id, Receipt.user_id == user.id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Ensure categories exist.
    categories = db.query(Category).filter(Category.user_id.is_(None)).all()
    categories_by_name = {c.name: c for c in categories}
    uncategorized = categories_by_name.get("Uncategorized")

    # Replace items with payload.
    receipt.items.clear()
    db.flush()

    for it in payload.items:
        if _is_junk_item(it.item_name, it.item_price):
            continue
        category_id = it.category_id if it.category_id is not None else (uncategorized.id if uncategorized else None)
        new_item = ReceiptItem(
            item_name=it.item_name,
            quantity=it.quantity,
            unit_price=it.unit_price,
            item_price=it.item_price,
            category_id=category_id,
            confidence_score=0.95,
        )
        receipt.items.append(new_item)

    receipt.processing_status = ReceiptStatus.confirmed.value
    receipt.processing_error = None
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    # Update per-user product stats for inventory and recommendations.
    from datetime import datetime, timezone

    from app.db.models import InventoryItem, Product
    from app.services.product_normalization import normalize_product_name

    purchased_at = receipt.receipt_date or datetime.now(timezone.utc).replace(tzinfo=None)

    for it in receipt.items:
        norm = normalize_product_name(it.item_name)
        if not norm:
            continue

        product = (
            db.query(Product)
            .filter(Product.user_id == user.id, Product.name_normalized == norm)
            .first()
        )
        if product is None:
            # Fuzzy match for near-duplicates (receipt OCR variance).
            try:
                from difflib import SequenceMatcher

                # Only consider recent/common products to keep this fast.
                candidates = (
                    db.query(Product)
                    .filter(Product.user_id == user.id)
                    .order_by(Product.id.desc())
                    .limit(400)
                    .all()
                )
                best = None
                best_ratio = 0.0
                for c in candidates:
                    r = SequenceMatcher(None, norm, c.name_normalized).ratio()
                    if r > best_ratio:
                        best_ratio = r
                        best = c
                if best is not None and best_ratio >= 0.90:
                    product = best
            except Exception:
                pass
        if product is None:
            product = Product(
                user_id=user.id,
                name=it.item_name[:255],
                name_normalized=norm[:255],
                category_id=it.category_id,
            )
            db.add(product)
            db.flush()
        elif product.category_id is None and it.category_id is not None:
            product.category_id = it.category_id

        inv = db.query(InventoryItem).filter(InventoryItem.product_id == product.id).first()
        if inv is None:
            inv = InventoryItem(
                user_id=user.id,
                product_id=product.id,
                last_purchased_at=purchased_at,
                purchase_count=1,
                avg_interval_days=None,
            )
            db.add(inv)
        else:
            # Update running avg interval in days.
            prev_last = inv.last_purchased_at
            prev_count = inv.purchase_count or 0
            if prev_last is not None and purchased_at > prev_last:
                interval_days = (purchased_at - prev_last).total_seconds() / 86400.0
                if interval_days > 0.01:
                    if inv.avg_interval_days is None:
                        inv.avg_interval_days = interval_days
                    else:
                        # avg over (prev_count-1) intervals, adding one new interval
                        prev_intervals = max(prev_count - 1, 1)
                        inv.avg_interval_days = (
                            inv.avg_interval_days * prev_intervals + interval_days
                        ) / (prev_intervals + 1)

            inv.last_purchased_at = purchased_at
            inv.purchase_count = prev_count + 1
            inv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        db.add(product)
        db.add(inv)

    db.commit()
    return _get_receipt_out(receipt)

