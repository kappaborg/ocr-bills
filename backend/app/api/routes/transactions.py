from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Category, Receipt, ReceiptItem, ReceiptStatus
from app.schemas.transactions import TransactionOut, TransactionsListResponse


router = APIRouter()


@router.get("", response_model=TransactionsListResponse)
def list_transactions(
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    store: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    q = (
        db.query(Receipt, ReceiptItem, Category)
        .join(ReceiptItem, ReceiptItem.receipt_id == Receipt.id)
        .outerjoin(Category, Category.id == ReceiptItem.category_id)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
    )

    if from_date is not None:
        q = q.filter(Receipt.receipt_date >= from_date)
    if to_date is not None:
        q = q.filter(Receipt.receipt_date <= to_date)
    if category_id is not None:
        q = q.filter(ReceiptItem.category_id == category_id)
    if store:
        q = q.filter(Receipt.store_name.ilike(f"%{store}%"))

    rows = q.order_by(Receipt.receipt_date.desc().nullslast(), Receipt.id.desc()).limit(500).all()

    results: list[TransactionOut] = []
    for receipt, item, category in rows:
        results.append(
            TransactionOut(
                id=item.id,
                receipt_id=receipt.id,
                date=receipt.receipt_date,
                store_name=receipt.store_name,
                item_name=item.item_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                item_price=item.item_price,
                category_name=category.name if category else None,
            )
        )

    return {"results": results}

