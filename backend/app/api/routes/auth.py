from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.services.rate_limit import live_ocr_limiter
from app.utils.auth import create_access_token, hash_password, verify_password


router = APIRouter()

MIN_PASSWORD_LEN = 8


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdateRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):

    ip = request.client.host if request.client else "unknown"
    if not live_ocr_limiter.allow(f"register:{ip}", capacity=5, refill_per_sec=5 / 60.0):
        raise HTTPException(status_code=429, detail="Too many registration attempts. Please wait a minute.")

    if len(payload.password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LEN} characters.",
        )

    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):

    ip = request.client.host if request.client else "unknown"
    if not live_ocr_limiter.allow(f"login:{ip}", capacity=10, refill_per_sec=10 / 60.0):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait 60 seconds before trying again.")

    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.patch("/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(payload.new_password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"New password must be at least {MIN_PASSWORD_LEN} characters.",
        )

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"detail": "Password updated successfully"}


@router.get("/me")
def get_me(
    user: User = Depends(get_current_user),
):
    return {"id": user.id, "email": user.email}


@router.get("/me/export")
def export_my_data(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    GDPR-style export: dump everything we have for this user as JSON.
    Includes receipts (with items), products, inventory, budgets, household
    memberships. Does NOT include the password hash or Stripe customer ID —
    those are sensitive and not part of the "data subject" record.
    """
    from datetime import datetime
    from app.db.models import (
        Receipt, ReceiptItem, Product, InventoryItem, Budget,
        HouseholdMember, Subscription, Category,
    )

    def _iso(dt):
        return dt.isoformat() if isinstance(dt, datetime) else dt

    receipts = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id)
        .all()
    )
    receipts_out = []
    for r in receipts:
        receipts_out.append({
            "id": r.id,
            "store_name": r.store_name,
            "total_amount": r.total_amount,
            "currency": r.currency,
            "tax_amount": r.tax_amount,
            "receipt_date": _iso(r.receipt_date),
            "detected_language": r.detected_language,
            "processing_status": r.processing_status,
            "created_at": _iso(r.created_at),
            "items": [
                {
                    "item_name": it.item_name,
                    "item_price": it.item_price,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "category_id": it.category_id,
                }
                for it in (r.items or [])
            ],
        })

    products = db.query(Product).filter(Product.user_id == user.id).all()
    inventory = db.query(InventoryItem).filter(InventoryItem.user_id == user.id).all()
    budgets = db.query(Budget).filter(Budget.user_id == user.id).all()
    memberships = db.query(HouseholdMember).filter(HouseholdMember.user_id == user.id).all()
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    user_cats = db.query(Category).filter(Category.user_id == user.id).all()

    return {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "user": {"id": user.id, "email": user.email, "created_at": _iso(user.created_at)},
        "subscription": (
            None if sub is None else {
                "plan": sub.plan,
                "status": sub.status,
                "current_period_end": _iso(sub.current_period_end),
            }
        ),
        "receipts": receipts_out,
        "products": [{"id": p.id, "name": p.name, "category_id": p.category_id} for p in products],
        "inventory": [
            {
                "product_id": i.product_id,
                "last_purchased_at": _iso(i.last_purchased_at),
                "purchase_count": i.purchase_count,
                "avg_interval_days": i.avg_interval_days,
            }
            for i in inventory
        ],
        "budgets": [
            {
                "category_id": b.category_id,
                "monthly_limit": b.monthly_limit,
                "currency": b.currency,
            }
            for b in budgets
        ],
        "household_memberships": [
            {"household_id": m.household_id, "role": m.role}
            for m in memberships
        ],
        "custom_categories": [{"id": c.id, "name": c.name} for c in user_cats],
    }


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Permanently delete the user and everything they own. Cascade chain:
    user → receipts → items (cascade), products → inventory (cascade), budgets,
    subscription, household memberships, user-owned categories.

    Stripe subscription is NOT canceled automatically — the user should cancel
    via the customer portal first. (Stripe will keep billing them otherwise,
    and we can't refund retroactively.)
    """
    from app.db.models import (
        Receipt, Product, InventoryItem, Budget, Subscription,
        HouseholdMember, Category,
    )

    # The order matters: child rows first, then parents.
    db.query(InventoryItem).filter(InventoryItem.user_id == user.id).delete(synchronize_session=False)
    db.query(Product).filter(Product.user_id == user.id).delete(synchronize_session=False)
    db.query(Budget).filter(Budget.user_id == user.id).delete(synchronize_session=False)
    db.query(HouseholdMember).filter(HouseholdMember.user_id == user.id).delete(synchronize_session=False)
    db.query(Subscription).filter(Subscription.user_id == user.id).delete(synchronize_session=False)
    db.query(Category).filter(Category.user_id == user.id).delete(synchronize_session=False)
    # Receipts have cascade="all, delete-orphan" on items, so deleting Receipt
    # rows removes their items via the ORM relationship — use session.delete
    # so cascade fires, not the bulk delete().
    for r in db.query(Receipt).filter(Receipt.user_id == user.id).all():
        db.delete(r)
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
