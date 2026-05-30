import os
import re
import uuid

from datetime import date as _date, datetime, timedelta

import asyncio
import json as _json

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.api.deps import enforce_quota, get_current_user, get_db
from app.core.config import settings
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
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB per file

_JUNK_KEYWORDS = {
    "UKUPNO", "UPLACENO", "UPLATENO", "GOTOVINA", "POVRAT",
    "TOTAL", "TOIAL", "CHANGE", "CASH", "CARD", "AMOUNT",
    "JIB", "PIB", "IBF", "PDV", "VAT", "OSN", "POV",
    "FISKAL", "RACUN", "RAČUN",
}


def _is_junk_item(item_name: str, item_price: float) -> bool:
    name = (item_name or "").strip()
    name_upper = name.upper()

    if sum(ch.isalpha() for ch in name) < 2:
        return True
    if item_price <= 0 or item_price > 100_000:
        return True
    if any(kw in name_upper for kw in _JUNK_KEYWORDS):
        return True
    if re.search(r"\b(JIB|PIB|IBF|PDV|VAT)\s*[:=]", name, flags=re.IGNORECASE):
        return True
    from app.services.receipt_parser import detect_receipt_date
    if detect_receipt_date(name) is not None:
        return True
    return False


def _storage_path(storage_key: str) -> str:
    return os.path.join(settings.UPLOAD_DIR, storage_key)


def _load_receipt(receipt_id: int, user_id: int, db: Session) -> Receipt:
    """Load a receipt with items+categories eagerly to avoid N+1 queries."""
    receipt = (
        db.query(Receipt)
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.category))
        .filter(Receipt.id == receipt_id, Receipt.user_id == user_id)
        .first()
    )
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


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
        tax_amount=receipt.tax_amount,
        items=items_out,
    )


def _build_preview_out(raw_text: str, db: Session) -> ReceiptOut:
    lang = detect_language(raw_text)
    parsed = parse_receipt(raw_text)

    categories = db.query(Category).filter(Category.user_id.is_(None)).all()
    categories_by_name = {c.name: c.id for c in categories}

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
    _quota=Depends(enforce_quota),  # 402 when this period's receipt cap is reached
):

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results: list[dict] = []
    for uf in files:
        if uf.size is not None and uf.size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        ext = os.path.splitext(uf.filename or "")[1].lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: jpg, jpeg, png.",
            )

        receipt_code = uuid.uuid4().hex
        # Sanitize the client-supplied filename — strip any path components
        # and reject anything that's not a safe character. Prevents traversal
        # via filenames like "../../etc/shadow.jpg".
        safe_name = re.sub(r"[^\w.\-]+", "_", os.path.basename(uf.filename or "receipt.jpg"))
        storage_key = f"{user.id}/{receipt_code}/{safe_name}"

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

        # FastAPI always injects BackgroundTasks — no null guard needed
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

    ip = request.client.host if request.client else "unknown"
    if not live_ocr_limiter.allow(
        f"live-preview:{user.id}:{ip}",
        capacity=12,
        refill_per_sec=12 / 10.0,
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
    _quota=Depends(enforce_quota),
):

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

    background_tasks.add_task(process_receipt, receipt.id)

    return {"receipt_id": receipt.id, "processing_status": receipt.processing_status}


@router.get("/search")
def search_receipts(
    q: str = Query(..., min_length=1, max_length=200, description="Free-text search"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Multi-token search across receipt raw_text, store_name, and line items.
    Tokens are AND-ed; case-insensitive; matches any token in any field.
    """
    tokens = [t for t in q.split() if t]
    if not tokens:
        return {"results": []}

    from sqlalchemy import and_, or_

    conditions = []
    for tok in tokens:
        pattern = f"%{tok}%"
        token_cond = or_(
            Receipt.raw_text.ilike(pattern),
            Receipt.store_name.ilike(pattern),
            Receipt.id.in_(
                db.query(ReceiptItem.receipt_id).filter(ReceiptItem.item_name.ilike(pattern))
            ),
        )
        conditions.append(token_cond)

    receipts = (
        db.query(Receipt)
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.category))
        .filter(Receipt.user_id == user.id)
        .filter(and_(*conditions))
        .order_by(Receipt.receipt_date.desc().nullslast(), Receipt.id.desc())
        .limit(50)
        .all()
    )
    return {"results": [_get_receipt_out(r) for r in receipts]}


@router.get("/check-duplicate")
def check_duplicate(
    store_name: str = Query(..., max_length=255),
    total_amount: float = Query(..., gt=0),
    receipt_date: str = Query(..., description="ISO 8601 date or datetime"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Returns the existing receipt_id if a likely duplicate exists for this user,
    matching on (store name case-insensitive, total ±1% tolerance, same calendar day).
    """
    try:
        dt = datetime.fromisoformat(receipt_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid receipt_date — must be ISO 8601")

    day_start = datetime.combine(dt.date(), datetime.min.time())
    day_end = day_start + timedelta(days=1)
    tol = max(0.01, total_amount * 0.01)

    existing = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.store_name.ilike(store_name))
        .filter(Receipt.total_amount.between(total_amount - tol, total_amount + tol))
        .filter(Receipt.receipt_date >= day_start, Receipt.receipt_date < day_end)
        .first()
    )
    if existing is None:
        return {"duplicate": False}
    return {
        "duplicate": True,
        "receipt_id": existing.id,
        "store_name": existing.store_name,
        "total_amount": existing.total_amount,
        "receipt_date": existing.receipt_date,
    }


# ─── Sample data ────────────────────────────────────────────────────────────
# A 1-click "try with sample data" feature for empty dashboards. Receipts are
# created with their store_name prefixed by SAMPLE_PREFIX so the user can wipe
# only the sample data later without touching anything real they uploaded.

SAMPLE_PREFIX = "Sample — "

# 7 curated receipts engineered so the dashboard shows budgets, insights
# (frequency-spike, price-change), recurring detection, and multi-currency
# all at once. Dates are relative to "now" at request time.
_SAMPLE_RECEIPTS: list[dict] = [
    # 25 days ago — first Konzum visit (price baseline)
    {
        "days_ago": 25, "store": "Konzum", "currency": "BAM", "lang": "bs",
        "category": "Groceries", "total": 28.50,
        "items": [
            ("Hljeb crni 500g", 1, 1.50, 1.50),
            ("Mlijeko 2.8% 1L", 1, 2.20, 2.20),
            ("Jogurt prirodni", 1, 1.80, 1.80),
            ("Banane 1kg", 1, 3.20, 3.20),
            ("Kafa Franck 250g", 1, 8.50, 8.50),
            ("Jaja 10kom", 1, 4.30, 4.30),
            ("Sir Trapist 200g", 1, 4.50, 4.50),
            ("Šećer 1kg", 1, 2.50, 2.50),
        ],
    },
    # 18 days ago — Bingo grocery
    {
        "days_ago": 18, "store": "Bingo", "currency": "BAM", "lang": "bs",
        "category": "Groceries", "total": 41.20,
        "items": [
            ("Pile cijelo 1.5kg", 1, 12.50, 12.50),
            ("Krompir 2kg", 1, 3.60, 3.60),
            ("Paradajz 1kg", 1, 4.20, 4.20),
            ("Hljeb bijeli", 1, 1.50, 1.50),
            ("Mlijeko 2.8% 1L", 1, 2.20, 2.20),
            ("Riža 1kg", 1, 3.50, 3.50),
            ("Ulje suncokretovo 1L", 1, 5.20, 5.20),
            ("Maslac 250g", 1, 4.80, 4.80),
            ("Jaja 10kom", 1, 3.70, 3.70),
        ],
    },
    # 12 days ago — gas station (Transportation)
    {
        "days_ago": 12, "store": "PETRO", "currency": "BAM", "lang": "sr",
        "category": "Transportation", "total": 60.00,
        "items": [("Eurosuper BMB 95 30L", 30, 2.00, 60.00)],
    },
    # 9 days ago — Russian receipt, multi-currency showcase
    {
        "days_ago": 9, "store": "Магнит", "currency": "RUB", "lang": "ru",
        "category": "Groceries", "total": 844.50,
        "items": [
            ("Хлеб ржаной", 1, 35.50, 35.50),
            ("Молоко 1L", 1, 89.00, 89.00),
            ("Сыр Российский 200г", 1, 250.00, 250.00),
            ("Колбаса докторская", 1, 350.00, 350.00),
            ("Чай Майский", 1, 120.00, 120.00),
        ],
    },
    # 7 days ago — pharmacy (Healthcare)
    {
        "days_ago": 7, "store": "Apoteka MUP", "currency": "BAM", "lang": "bs",
        "category": "Healthcare", "total": 18.40,
        "items": [
            ("Aspirin 100mg 30tbl", 1, 6.80, 6.80),
            ("Vitamin C 1000mg", 1, 6.60, 6.60),
            ("Maska zaštitna 5kom", 1, 5.00, 5.00),
        ],
    },
    # 5 days ago — second Konzum visit, MILK PRICE BUMPED 2.20 → 2.65
    # (drives the price_increase insight)
    {
        "days_ago": 5, "store": "Konzum", "currency": "BAM", "lang": "bs",
        "category": "Groceries", "total": 22.65,
        "items": [
            ("Hljeb crni 500g", 1, 1.50, 1.50),
            ("Mlijeko 2.8% 1L", 1, 2.65, 2.65),   # was 2.20 → flagged as price increase
            ("Jogurt prirodni", 1, 1.80, 1.80),
            ("Banane 1kg", 1, 3.20, 3.20),
            ("Jaja 10kom", 1, 4.30, 4.30),
            ("Voda 1.5L", 1, 1.20, 1.20),
            ("Bombone", 1, 1.00, 1.00),
            ("Tjestenina", 1, 1.90, 1.90),
            ("Sir Trapist 200g", 1, 4.50, 4.50),  # round to 22.65
        ],
    },
    # 2 days ago — cafe (Entertainment)
    {
        "days_ago": 2, "store": "Cafe Tito", "currency": "BAM", "lang": "bs",
        "category": "Entertainment", "total": 14.50,
        "items": [
            ("Espresso", 2, 2.00, 4.00),
            ("Croissant", 2, 2.50, 5.00),
            ("Sok narandža", 2, 2.75, 5.50),
        ],
    },
]


def _generate_sample_raw_text(spec: dict, dt: datetime) -> str:
    lines = [
        spec["store"].upper(),
        f"({SAMPLE_PREFIX.strip()} sample receipt for demo)",
        dt.strftime("%d.%m.%Y %H:%M"),
        "-" * 30,
    ]
    for name, qty, unit, total in spec["items"]:
        if qty != 1:
            lines.append(f"{name}  {qty}x{unit:.2f}  {total:.2f}")
        else:
            lines.append(f"{name}  {total:.2f}")
    lines += ["-" * 30, f"UKUPNO  {spec['total']:.2f} {spec['currency']}"]
    return "\n".join(lines)


@router.post("/samples")
def load_sample_data(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Idempotent: if the user already has sample receipts (prefix detection), no-op.
    Otherwise inserts 7 curated receipts + 2 budgets so the dashboard isn't empty.
    """
    existing = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.store_name.like(f"{SAMPLE_PREFIX}%"))
        .count()
    )
    if existing > 0:
        return {"already_loaded": True, "count": existing}

    # Look up category IDs once
    categories = {c.name: c.id for c in db.query(Category).filter(Category.user_id.is_(None)).all()}

    now = datetime.utcnow()
    created_count = 0
    for spec in _SAMPLE_RECEIPTS:
        receipt_date = now - timedelta(days=spec["days_ago"])
        store_label = f"{SAMPLE_PREFIX}{spec['store']}"

        receipt = Receipt(
            user_id=user.id,
            storage_key=f"{user.id}/sample/{uuid.uuid4().hex}.jpg",
            raw_text=_generate_sample_raw_text(spec, receipt_date),
            detected_language=spec["lang"],
            receipt_date=receipt_date,
            store_name=store_label,
            total_amount=spec["total"],
            currency=spec["currency"],
            processing_status=ReceiptStatus.confirmed.value,
            created_at=receipt_date,
            updated_at=receipt_date,
        )
        db.add(receipt)
        db.flush()

        cat_id = categories.get(spec["category"])
        for item_name, qty, unit_price, item_price in spec["items"]:
            db.add(ReceiptItem(
                receipt_id=receipt.id,
                item_name=item_name,
                quantity=float(qty),
                unit_price=float(unit_price),
                item_price=float(item_price),
                category_id=cat_id,
                confidence_score=0.95,
            ))
        created_count += 1

    # Also pre-create a couple of budgets for the Pro feature (they'll show
    # "spent vs budget" against the sample data). These are tagged via a
    # special note in the currency field — no clean way without schema change,
    # so we accept that "clearing samples" doesn't auto-remove budgets. Users
    # can edit/delete them manually from the dashboard.
    from app.db.models import Budget
    sample_budgets = [
        ("Groceries", 200.00),
        ("Transportation", 100.00),
    ]
    for cat_name, limit in sample_budgets:
        cat_id = categories.get(cat_name)
        if not cat_id:
            continue
        # Skip if user already has a budget for this category
        existing_b = (
            db.query(Budget)
            .filter(Budget.user_id == user.id, Budget.category_id == cat_id)
            .first()
        )
        if existing_b:
            continue
        db.add(Budget(
            user_id=user.id,
            category_id=cat_id,
            monthly_limit=limit,
            currency="BAM",
        ))

    db.commit()
    return {"already_loaded": False, "count": created_count}


@router.delete("/samples", status_code=status.HTTP_204_NO_CONTENT)
def clear_sample_data(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Remove only receipts the user got from the sample-data feature. User-uploaded
    receipts are untouched. Budgets are left in place because they may have been
    edited.
    """
    receipts = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.store_name.like(f"{SAMPLE_PREFIX}%"))
        .all()
    )
    for r in receipts:
        db.delete(r)  # cascade drops items
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/samples/status")
def sample_data_status(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Tells the frontend whether sample data is currently loaded for this user."""
    count = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.store_name.like(f"{SAMPLE_PREFIX}%"))
        .count()
    )
    return {"loaded": count > 0, "count": count}


@router.get("", response_model=list[ReceiptOut])
def list_receipts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    receipts = (
        db.query(Receipt)
        .options(selectinload(Receipt.items))
        .filter(Receipt.user_id == user.id)
        .order_by(Receipt.id.desc())
        .limit(50)
        .all()
    )
    return [_get_receipt_out(r) for r in receipts]


@router.get("/{receipt_id}/image")
def get_receipt_image(
    receipt_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id, Receipt.user_id == user.id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    file_path = _storage_path(receipt.storage_key)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    ext = os.path.splitext(file_path)[1].lower()
    media_type = "image/png" if ext == ".png" else "image/jpeg"

    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{receipt_id}/thumbnail")
def get_receipt_thumbnail(
    receipt_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Serves a 200x200 JPEG thumbnail of the receipt image.

    Generated on first request, cached on disk next to the original
    (`{original}.thumb.jpg`). Subsequent requests skip Pillow and serve the
    cached file directly. Tiny payload (~10-20 KB) for list-view rendering.
    """
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id, Receipt.user_id == user.id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    original_path = _storage_path(receipt.storage_key)
    if not os.path.exists(original_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    thumb_path = original_path + ".thumb.jpg"
    if not os.path.exists(thumb_path):
        try:
            from PIL import Image, ImageOps
            with Image.open(original_path) as src:
                # Respect phone-camera rotation so the thumbnail isn't sideways.
                src = ImageOps.exif_transpose(src)
                src = src.convert("RGB")
                # Cover-fit into a 200x200 square; ImageOps.fit does center-crop
                # which looks much better than letterbox for receipt grids.
                thumb = ImageOps.fit(src, (200, 200), method=Image.Resampling.LANCZOS)
                thumb.save(thumb_path, "JPEG", quality=78, optimize=True)
        except Exception as e:
            # Don't 500 on thumbnail failure — log + fall back to original.
            # (List views will be slower but still work.)
            raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {e}")

    return FileResponse(
        thumb_path,
        media_type="image/jpeg",
        headers={
            # Thumbnails are immutable per receipt — long cache + immutable hint.
            "Cache-Control": "private, max-age=86400, immutable",
        },
    )


@router.get("/{receipt_id}", response_model=ReceiptOut)
def get_receipt(receipt_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    receipt = _load_receipt(receipt_id, user.id, db)
    return _get_receipt_out(receipt)


# Terminal statuses — the SSE stream emits one final event then closes.
_TERMINAL_STATUSES = {"parsed", "confirmed", "error"}


@router.get("/{receipt_id}/events")
async def receipt_events(
    receipt_id: int,
    user=Depends(get_current_user),
):
    """
    Server-Sent Events stream for a single receipt's processing status.

    Emits one event per status transition (`queued` → `processing` → `parsed`
    / `error` / `confirmed`). Closes when status is terminal or after ~60s
    of total wall time (whichever comes first). Heartbeats every 15s to keep
    intermediaries from buffering or timing out.

    The frontend subscribes via EventSource and updates UI inline. Polling
    remains the fallback for clients without EventSource.
    """
    async def event_stream():
        # Open a fresh DB session per request — we can't reuse the dep-injected
        # session inside a long-running generator because FastAPI closes it after
        # the response starts streaming.
        from app.db.session import SessionLocal

        last_status: str | None = None
        last_heartbeat = 0.0
        total_elapsed = 0.0
        poll_every = 0.5            # seconds
        heartbeat_every = 15.0      # seconds
        max_duration = 60.0         # seconds — generous OCR ceiling

        while total_elapsed < max_duration:
            # Pull primitives inside the session — the ORM object can't be
            # touched once the session closes (lazy loads raise
            # DetachedInstanceError otherwise).
            db = SessionLocal()
            try:
                receipt = (
                    db.query(Receipt)
                    .options(selectinload(Receipt.items))
                    .filter(Receipt.id == receipt_id, Receipt.user_id == user.id)
                    .first()
                )
                if receipt is None:
                    snapshot = None
                else:
                    snapshot = {
                        "status": receipt.processing_status or "queued",
                        "processing_error": receipt.processing_error,
                        "store_name": receipt.store_name,
                        "total_amount": receipt.total_amount,
                        "currency": receipt.currency,
                        "items_count": len(receipt.items or []),
                    }
            finally:
                db.close()

            if snapshot is None:
                yield "event: gone\ndata: {}\n\n"
                return

            status_now = snapshot["status"]
            if status_now != last_status:
                yield f"event: status\ndata: {_json.dumps(snapshot)}\n\n"
                last_status = status_now
                if status_now in _TERMINAL_STATUSES:
                    return

            if total_elapsed - last_heartbeat >= heartbeat_every:
                yield ": heartbeat\n\n"  # SSE comment; keeps the pipe warm
                last_heartbeat = total_elapsed

            await asyncio.sleep(poll_every)
            total_elapsed += poll_every

        # Timed out — final status emit so the client knows we gave up.
        yield f"event: timeout\ndata: {_json.dumps({'last_status': last_status})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",     # tells nginx not to buffer SSE
            "Connection": "keep-alive",
        },
    )


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id, Receipt.user_id == user.id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Remove stored file
    file_path = _storage_path(receipt.storage_key)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass

    db.delete(receipt)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{receipt_id}/confirm", response_model=ReceiptOut)
def confirm_receipt(
    receipt_id: int,
    payload: ReceiptConfirmRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    receipt = _load_receipt(receipt_id, user.id, db)

    categories = db.query(Category).filter(Category.user_id.is_(None)).all()
    categories_by_name = {c.name: c for c in categories}
    uncategorized = categories_by_name.get("Uncategorized")

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

    from app.services.inventory_update import update_inventory_for_receipt
    update_inventory_for_receipt(receipt, db)

    # Drop the cached user-context so the next OCR call sees this freshly
    # confirmed receipt in the user's history.
    from app.services.user_context import invalidate as _invalidate_ctx
    _invalidate_ctx(receipt.user_id)

    db.refresh(receipt)
    return _get_receipt_out(receipt)
