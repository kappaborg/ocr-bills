"""
Monthly budgets per category, with progress + projection.

Conversion: each transaction's price is converted from its receipt's currency
into the budget's currency using the FX cache (frankfurter + fallback).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_plan
from app.api.routes.fx import get_rates
from app.db.models import Budget, Category, Receipt, ReceiptItem, ReceiptStatus


router = APIRouter(dependencies=[Depends(require_plan("pro"))])


class BudgetIn(BaseModel):
    category_id: Optional[int] = None  # None = overall budget
    monthly_limit: float
    currency: str = "BAM"


class BudgetOut(BaseModel):
    id: int
    category_id: Optional[int]
    category_name: Optional[str]
    monthly_limit: float
    currency: str
    spent: float
    remaining: float
    percent: float          # 0–100 (can exceed 100 when over)
    projected_month_end: float
    over_budget: bool


def _month_window(now: datetime) -> tuple[datetime, datetime, int, int]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    days_so_far = max(1, (now - start).days + 1)
    days_in_month = (end - start).days
    return start, end, days_so_far, days_in_month


def _convert(amount: float, from_ccy: str | None, to_ccy: str, rates: dict[str, float]) -> float:
    f = (from_ccy or "").upper()
    t = (to_ccy or "").upper()
    if not f or f == t:
        return amount
    fr = rates.get(f)
    tr = rates.get(t)
    if fr is None or tr is None or fr == 0:
        return amount  # best effort; caller's currency unknown
    return amount / fr * tr


def _compute_progress(budget: Budget, db: Session, rates: dict[str, float], now: datetime) -> BudgetOut:
    start, _end, days_so_far, days_in_month = _month_window(now)

    q = (
        db.query(ReceiptItem.item_price, Receipt.currency)
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .filter(Receipt.user_id == budget.user_id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(Receipt.receipt_date >= start)
    )
    if budget.category_id is not None:
        q = q.filter(ReceiptItem.category_id == budget.category_id)

    spent = sum(_convert(price, ccy, budget.currency, rates) for price, ccy in q.all())
    remaining = budget.monthly_limit - spent
    percent = 0.0 if budget.monthly_limit <= 0 else spent / budget.monthly_limit * 100.0
    projected = spent * days_in_month / days_so_far

    return BudgetOut(
        id=budget.id,
        category_id=budget.category_id,
        category_name=budget.category.name if budget.category else None,
        monthly_limit=budget.monthly_limit,
        currency=budget.currency,
        spent=round(spent, 2),
        remaining=round(remaining, 2),
        percent=round(percent, 1),
        projected_month_end=round(projected, 2),
        over_budget=spent > budget.monthly_limit,
    )


@router.get("")
def list_budgets(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rates = get_rates()["rates"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    budgets = db.query(Budget).filter(Budget.user_id == user.id).all()
    return {"results": [_compute_progress(b, db, rates, now) for b in budgets]}


@router.post("")
def upsert_budget(
    payload: BudgetIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if payload.monthly_limit <= 0:
        raise HTTPException(status_code=400, detail="monthly_limit must be > 0")

    if payload.category_id is not None:
        # Categories are either global (user_id IS NULL) or owned by a user.
        # Reject attempts to pin a budget to another user's private category.
        from sqlalchemy import or_
        cat = (
            db.query(Category)
            .filter(Category.id == payload.category_id)
            .filter(or_(Category.user_id.is_(None), Category.user_id == user.id))
            .first()
        )
        if cat is None:
            raise HTTPException(status_code=404, detail="Category not found")

    existing = (
        db.query(Budget)
        .filter(Budget.user_id == user.id, Budget.category_id == payload.category_id)
        .first()
    )
    if existing:
        existing.monthly_limit = payload.monthly_limit
        existing.currency = payload.currency.upper()
        existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        budget = existing
    else:
        budget = Budget(
            user_id=user.id,
            category_id=payload.category_id,
            monthly_limit=payload.monthly_limit,
            currency=payload.currency.upper(),
        )
        db.add(budget)
    db.commit()
    db.refresh(budget)

    rates = get_rates()["rates"]
    return _compute_progress(budget, db, rates, datetime.now(timezone.utc).replace(tzinfo=None))


@router.delete("/{budget_id}")
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    budget = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == user.id).first()
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()
    return {"detail": "deleted"}
