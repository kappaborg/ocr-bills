from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Receipt, ReceiptItem, ReceiptStatus
from app.schemas.insights import InsightOut, InsightsListResponse
from app.services.product_normalization import normalize_product_name


router = APIRouter()


@router.get("", response_model=InsightsListResponse)
def list_insights(db: Session = Depends(get_db), user=Depends(get_current_user)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    last_30 = now - timedelta(days=30)
    last_7 = now - timedelta(days=7)
    prev_7 = now - timedelta(days=14)

    # Frequency: item_name count in last 30 days.
    freq_q = (
        db.query(ReceiptItem.item_name, func.count(ReceiptItem.id))
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(Receipt.receipt_date >= last_30)
        .group_by(ReceiptItem.item_name)
        .order_by(func.count(ReceiptItem.id).desc())
        .limit(10)
    )

    insights: list[InsightOut] = []
    for name, count in freq_q.all():
        if count >= 3 and name:
            insights.append(
                InsightOut(
                    id=-1,
                    type="frequency_spike",
                    message=f"You bought '{name}' {count} times in the last 30 days.",
                    metadata_json={"item_name": name, "count": count},
                    created_at=now,
                )
            )
            break

    # Spending spike: compare last 7 days vs previous 7 days.
    sum_q = (
        db.query(func.sum(ReceiptItem.item_price))
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(Receipt.receipt_date.isnot(None))
    )

    current_total = sum_q.filter(Receipt.receipt_date >= last_7).scalar() or 0.0
    previous_total = sum_q.filter(Receipt.receipt_date >= prev_7, Receipt.receipt_date < last_7).scalar() or 0.0

    if previous_total > 0 and current_total > previous_total * 1.2:
        insights.append(
            InsightOut(
                id=-2,
                type="spending_spike",
                message=f"Spending increased this week (+{((current_total - previous_total) / previous_total) * 100:.0f}% vs last week).",
                metadata_json={
                    "current_total": current_total,
                    "previous_total": previous_total,
                },
                created_at=now,
            )
        )

    # Price-change: for each (store, normalized product) with ≥2 purchases in the
    # last 90 days, compare the most recent unit_price to the previous one. Surface
    # only changes >= 10% (in either direction) and only the largest one.
    last_90 = now - timedelta(days=90)
    price_rows = (
        db.query(
            Receipt.store_name,
            ReceiptItem.item_name,
            ReceiptItem.unit_price,
            Receipt.receipt_date,
        )
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(Receipt.receipt_date >= last_90)
        .filter(Receipt.receipt_date.isnot(None))
        .filter(ReceiptItem.unit_price.isnot(None))
        .filter(ReceiptItem.unit_price > 0)
        .order_by(Receipt.receipt_date.asc())
        .all()
    )

    grouped: dict[tuple[str, str], list[tuple[datetime, float]]] = {}
    for store, name, unit_price, date in price_rows:
        if not store or not name:
            continue
        norm = normalize_product_name(name)
        if not norm:
            continue  # Skip items whose normalized form is empty (avoid bogus pairs).
        key = (store, norm)
        grouped.setdefault(key, []).append((date, float(unit_price)))

    best_change: tuple[float, str, str, float, float] | None = None  # (abs_pct, store, name, old, new)
    for (store, _norm), purchases in grouped.items():
        if len(purchases) < 2:
            continue
        purchases.sort(key=lambda x: x[0])
        old_price = purchases[-2][1]
        new_price = purchases[-1][1]
        if old_price <= 0:
            continue
        pct = (new_price - old_price) / old_price * 100.0
        if abs(pct) < 10.0:
            continue
        # Find the display name (last seen) for the matching key by scanning
        # original rows — we kept normalized form to group.
        display_name = next(
            (n for s, n, _, _ in price_rows if s == store and normalize_product_name(n) == _norm),
            _norm,
        )
        if best_change is None or abs(pct) > best_change[0]:
            best_change = (abs(pct), store, display_name, old_price, new_price)

    if best_change is not None:
        abs_pct, store, name, old_price, new_price = best_change
        direction = "up" if new_price > old_price else "down"
        sign = "+" if new_price > old_price else "−"
        insights.append(
            InsightOut(
                id=-4,
                type="price_increase" if new_price > old_price else "info",
                message=(
                    f"'{name}' at {store}: {old_price:.2f} → {new_price:.2f} "
                    f"({sign}{abs_pct:.0f}% {direction})."
                ),
                metadata_json={
                    "product": name,
                    "store": store,
                    "old_price": old_price,
                    "new_price": new_price,
                    "pct": new_price > old_price and abs_pct or -abs_pct,
                },
                created_at=now,
            )
        )

    if not insights:
        # Baseline insight
        total_30 = sum_q.filter(Receipt.receipt_date >= last_30).scalar() or 0.0
        insights.append(
            InsightOut(
                id=-3,
                type="info",
                message=f"Your total spending in the last 30 days is {total_30:.2f}.",
                metadata_json={"total_30": total_30},
                created_at=now,
            )
        )

    return {"results": insights}

