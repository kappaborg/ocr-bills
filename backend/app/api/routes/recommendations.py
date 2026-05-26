import statistics
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.routes.fx import get_rates
from app.db.init_db import init_db
from app.db.models import Category, InventoryItem, Product, Receipt, ReceiptItem, ReceiptStatus
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


@router.get("/recurring")
def recurring(
    display_currency: str = Query(default="BAM", min_length=3, max_length=4),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Surface products that look like recurring/subscription purchases:
    bought ≥3 times, interval stddev ≤ 35% of mean, average interval ≤ 60 days.
    For each, compute the average spend per purchase and project a monthly cost
    in the requested display_currency using cached FX rates.
    """
    init_db(db)
    rates = get_rates()["rates"]
    to_ccy = display_currency.upper()
    to_rate = rates.get(to_ccy)

    def _convert(amount: float, from_ccy: str | None) -> float:
        if not amount:
            return 0.0
        f = (from_ccy or to_ccy).upper()
        fr = rates.get(f)
        if fr is None or to_rate is None:
            return amount
        return amount / fr * to_rate

    # Pull every confirmed line item with date, normalized name and currency.
    rows = (
        db.query(
            Product.id,
            Product.name,
            Product.name_normalized,
            Category.name.label("category_name"),
            Receipt.receipt_date,
            ReceiptItem.item_price,
            Receipt.currency,
        )
        .join(ReceiptItem, ReceiptItem.item_name == Product.name)  # by exact display name
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .outerjoin(Category, Category.id == Product.category_id)
        .filter(Product.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(Receipt.receipt_date.isnot(None))
        .all()
    )

    grouped: dict[int, dict] = {}
    for pid, name, _norm, cat_name, date, price, ccy in rows:
        g = grouped.setdefault(pid, {"name": name, "category": cat_name, "purchases": []})
        g["purchases"].append((date, float(price or 0.0), ccy))

    recurring_out = []
    forecast_monthly_total = 0.0
    for pid, g in grouped.items():
        purchases = sorted(g["purchases"], key=lambda x: x[0])
        if len(purchases) < 3:
            continue
        intervals = [
            (purchases[i][0] - purchases[i - 1][0]).total_seconds() / 86400.0
            for i in range(1, len(purchases))
        ]
        mean = statistics.mean(intervals)
        if mean <= 0 or mean > 60:
            continue
        # Coefficient of variation — lower = more regular. Surface anything
        # that's repeatedly purchased; the UI can sort by cv if it wants only
        # the most subscription-like patterns.
        stdev = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
        cv = stdev / mean if mean else 1.0
        if cv > 0.75:
            continue

        avg_price = sum(_convert(p, c) for _, p, c in purchases) / len(purchases)
        per_month = avg_price * (30.0 / mean)
        forecast_monthly_total += per_month
        recurring_out.append({
            "product_id": pid,
            "product_name": g["name"],
            "category_name": g["category"],
            "purchase_count": len(purchases),
            "avg_interval_days": round(mean, 1),
            "interval_cv": round(cv, 3),
            "avg_spend": round(avg_price, 2),
            "projected_monthly_spend": round(per_month, 2),
            "currency": to_ccy,
        })

    recurring_out.sort(key=lambda r: r["projected_monthly_spend"], reverse=True)
    return {
        "results": recurring_out,
        "forecast_monthly_total": round(forecast_monthly_total, 2),
        "currency": to_ccy,
    }

