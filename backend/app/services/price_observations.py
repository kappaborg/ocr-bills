"""
Emit anonymous price observations from a confirmed receipt.

Called once per receipt on FIRST confirmation only (the route guards
re-confirms the same way it guards inventory double-counting). Sample
receipts and zero/negative prices are skipped. A 24h dedup window per
(product, store, price) bounds spam and accidental duplicates.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import PriceObservation, Receipt
from app.services.product_normalization import normalize_product_name
from app.services.store_normalization import normalize_store_name

_SAMPLE_PREFIX = "Sample — "
_DEDUP_WINDOW_HOURS = 24
# Abuse bound: one receipt realistically has < 100 line items; anything
# beyond this is junk OCR and would pollute the shared feed.
_MAX_ITEMS_PER_RECEIPT = 100


def emit_observations_for_receipt(receipt: Receipt, db: Session) -> int:
    """Insert price observations for a confirmed receipt's items.
    Returns the number of observations created."""
    store_raw = receipt.store_name or ""
    if not store_raw or store_raw.startswith(_SAMPLE_PREFIX):
        return 0
    store_key = normalize_store_name(store_raw)
    if not store_key:
        return 0
    currency = (receipt.currency or "").upper()
    if not currency:
        return 0

    observed_at = receipt.receipt_date or datetime.now(timezone.utc).replace(tzinfo=None)
    dedup_floor = observed_at - timedelta(hours=_DEDUP_WINDOW_HOURS)
    dedup_ceil = observed_at + timedelta(hours=_DEDUP_WINDOW_HOURS)

    created = 0
    for it in receipt.items[:_MAX_ITEMS_PER_RECEIPT]:
        if not it.item_price or it.item_price <= 0:
            continue
        product_key = normalize_product_name(it.item_name)
        if not product_key:
            continue

        # Per-unit price is the comparable number across stores; fall back
        # to line total when quantity is 1/unknown.
        unit = it.unit_price
        if unit is None and it.quantity and it.quantity > 0:
            unit = it.item_price / it.quantity

        exists = (
            db.query(PriceObservation.id)
            .filter(
                PriceObservation.product_normalized == product_key,
                PriceObservation.store_normalized == store_key,
                PriceObservation.price == it.item_price,
                PriceObservation.observed_at >= dedup_floor,
                PriceObservation.observed_at <= dedup_ceil,
            )
            .first()
        )
        if exists:
            continue

        db.add(PriceObservation(
            product_normalized=product_key,
            store_normalized=store_key,
            store_display=store_raw[:255],
            price=it.item_price,
            currency=currency,
            unit_price=unit,
            observed_at=observed_at,
            source="receipt",
            receipt_item_id=it.id,
        ))
        created += 1

    if created:
        db.commit()
    return created
