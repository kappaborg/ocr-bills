from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Receipt, ReceiptItem, ReceiptStatus
from app.schemas.insights import InsightOut, InsightsListResponse


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

