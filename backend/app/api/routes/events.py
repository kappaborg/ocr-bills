"""
Lightweight product-analytics events from clients (price-chip taps etc.).
Auth'd + rate-limited so the table can't be flooded. Read access is via
the database directly for now — there is no listing endpoint by design.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import ClientEvent
from app.services.rate_limit import live_ocr_limiter

router = APIRouter()

_ALLOWED_KINDS = {"price_chip_tap"}


class EventIn(BaseModel):
    kind: str = Field(min_length=1, max_length=64)
    store: str | None = Field(default=None, max_length=255)
    product: str | None = Field(default=None, max_length=255)


@router.post("", status_code=status.HTTP_201_CREATED)
def record_event(
    payload: EventIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if payload.kind not in _ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail="Unknown event kind")
    # 60 events/min per user — taps are human-paced; anything faster is a bug
    # or abuse.
    if not live_ocr_limiter.allow(f"events:{user.id}", capacity=60, refill_per_sec=1.0):
        raise HTTPException(status_code=429, detail="Too many events")

    db.add(ClientEvent(user_id=user.id, kind=payload.kind, store=payload.store, product=payload.product))
    db.commit()
    return {"ok": True}
