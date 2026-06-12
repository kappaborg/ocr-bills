"""
The user's single active shopping list. Composes the Market Pulse stack:
items carry crowdsourced price_options so clients can group the list by
cheapest store ("At Bingo: milk, eggs — 4.80 KM").
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import ShoppingListItem
from app.schemas.shopping_list import (
    ShoppingItemIn,
    ShoppingItemOut,
    ShoppingItemPatch,
    ShoppingListResponse,
)
from app.services.price_lookup import price_options_for
from app.services.product_normalization import normalize_product_name

router = APIRouter()

_MAX_ITEMS = 100


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_out(item: ShoppingListItem, db: Session, user_id: int) -> dict:
    return {
        "id": item.id,
        "product_name": item.product_name,
        "quantity": item.quantity,
        "checked": item.checked,
        "source": item.source,
        "created_at": item.created_at,
        "price_options": price_options_for(
            item.product_normalized, db, requesting_user_id=user_id,
        ),
    }


@router.get("", response_model=ShoppingListResponse)
def get_list(db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.user_id == user.id)
        .order_by(ShoppingListItem.checked.asc(), ShoppingListItem.created_at.asc())
        .all()
    )
    return {"items": [_to_out(i, db, user.id) for i in items]}


@router.post("", response_model=ShoppingItemOut, status_code=status.HTTP_201_CREATED)
def add_item(
    payload: ShoppingItemIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    norm = normalize_product_name(payload.product_name)
    if not norm:
        raise HTTPException(status_code=400, detail="Product name carries no usable text")

    count = db.query(ShoppingListItem).filter(ShoppingListItem.user_id == user.id).count()
    if count >= _MAX_ITEMS:
        raise HTTPException(status_code=400, detail=f"List is full ({_MAX_ITEMS} items)")

    # Adding an existing unchecked product bumps quantity instead of duplicating.
    existing = (
        db.query(ShoppingListItem)
        .filter(
            ShoppingListItem.user_id == user.id,
            ShoppingListItem.product_normalized == norm,
            ShoppingListItem.checked.is_(False),
        )
        .first()
    )
    if existing is not None:
        existing.quantity += payload.quantity
        db.commit()
        db.refresh(existing)
        return _to_out(existing, db, user.id)

    item = ShoppingListItem(
        user_id=user.id,
        product_name=payload.product_name.strip(),
        product_normalized=norm,
        quantity=payload.quantity,
        source="manual",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item, db, user.id)


@router.post("/from-need-to-buy", response_model=ShoppingListResponse)
def add_due_items(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Bulk-add everything currently due per the recommender. Idempotent:
    products already on the list (unchecked) are skipped."""
    from app.api.routes.recommendations import need_to_buy

    due = need_to_buy(lead_days=2, db=db, user=user)["results"]

    existing_norms = {
        row[0]
        for row in db.query(ShoppingListItem.product_normalized)
        .filter(ShoppingListItem.user_id == user.id, ShoppingListItem.checked.is_(False))
        .all()
    }
    count = db.query(ShoppingListItem).filter(ShoppingListItem.user_id == user.id).count()
    for rec in due:
        norm = normalize_product_name(rec["product_name"])
        if not norm or norm in existing_norms or count >= _MAX_ITEMS:
            continue
        db.add(ShoppingListItem(
            user_id=user.id,
            product_name=rec["product_name"],
            product_normalized=norm,
            quantity=1.0,
            source="need_to_buy",
        ))
        existing_norms.add(norm)
        count += 1
    db.commit()
    return get_list(db=db, user=user)


@router.patch("/{item_id}", response_model=ShoppingItemOut)
def update_item(
    item_id: int,
    payload: ShoppingItemPatch,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    item = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.id == item_id, ShoppingListItem.user_id == user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if payload.checked is not None:
        item.checked = payload.checked
        item.checked_at = _now() if payload.checked else None
    if payload.quantity is not None:
        item.quantity = payload.quantity
    db.commit()
    db.refresh(item)
    return _to_out(item, db, user.id)


@router.delete("/checked", status_code=status.HTTP_204_NO_CONTENT)
def clear_checked(db: Session = Depends(get_db), user=Depends(get_current_user)):
    db.query(ShoppingListItem).filter(
        ShoppingListItem.user_id == user.id, ShoppingListItem.checked.is_(True)
    ).delete()
    db.commit()


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    deleted = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.id == item_id, ShoppingListItem.user_id == user.id)
        .delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    db.commit()