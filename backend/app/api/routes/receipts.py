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

    db.refresh(receipt)
    return _get_receipt_out(receipt)
