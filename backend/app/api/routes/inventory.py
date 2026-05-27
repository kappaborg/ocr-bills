from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Category, InventoryItem, Product
from app.schemas.inventory import InventoryListResponse


router = APIRouter()


@router.get("", response_model=InventoryListResponse)
def list_inventory(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        db.query(InventoryItem, Product, Category)
        .join(Product, Product.id == InventoryItem.product_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .filter(InventoryItem.user_id == user.id)
        .order_by(InventoryItem.last_purchased_at.desc().nullslast(), InventoryItem.id.desc())
        .limit(1000)
        .all()
    )

    results = []
    for inv, product, category in rows:
        next_expected = None
        if inv.last_purchased_at is not None and inv.avg_interval_days is not None:
            next_expected = inv.last_purchased_at + timedelta(days=float(inv.avg_interval_days))

        results.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "category_id": category.id if category else None,
                "category_name": category.name if category else None,
                "last_purchased_at": inv.last_purchased_at,
                "purchase_count": inv.purchase_count,
                "avg_interval_days": inv.avg_interval_days,
                "next_expected_buy_date": next_expected,
            }
        )

    return {"results": results}

