from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.init_db import init_db
from app.db.models import Category, InventoryItem, Product
from app.schemas.recommendations import NeedToBuyResponse


router = APIRouter()


@router.get("/need-to-buy", response_model=NeedToBuyResponse)
def need_to_buy(
    lead_days: int = Query(default=2, ge=0, le=30),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Simple baseline recommender:
    - If we have avg_interval_days, predict next expected buy date.
    - Recommend when now is within lead_days of that date (or overdue).
    """
    init_db(db)

    rows = (
        db.query(InventoryItem, Product, Category)
        .join(Product, Product.id == InventoryItem.product_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .filter(InventoryItem.user_id == user.id)
        .all()
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    results = []
    for inv, product, category in rows:
        if inv.last_purchased_at is None or inv.avg_interval_days is None:
            continue

        next_expected = inv.last_purchased_at + timedelta(days=float(inv.avg_interval_days))
        threshold = next_expected - timedelta(days=lead_days)
        if now < threshold:
            continue

        # Score: higher when more overdue.
        overdue_days = (now - next_expected).total_seconds() / 86400.0
        score = max(0.0, overdue_days) + 1.0

        results.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "category_name": category.name if category else None,
                "last_purchased_at": inv.last_purchased_at,
                "next_expected_buy_date": next_expected,
                "score": score,
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return {"results": results[:200]}

