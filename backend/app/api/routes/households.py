"""
Household sharing — group users so a receipt uploaded by anyone in the household
is visible to every member.

Join model is share-link based: the household has a single invite_token that
new members POST to /households/join. Lightweight and good enough for a demo;
production deployments should layer per-invite tokens + expirations on top.
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_plan
from app.db.init_db import init_db
from app.db.models import Household, HouseholdMember, Receipt, User


router = APIRouter(dependencies=[Depends(require_plan("business"))])


class HouseholdIn(BaseModel):
    name: str


class JoinRequest(BaseModel):
    invite_token: str


class MemberOut(BaseModel):
    user_id: int
    email: str
    role: str


def _household_out(household: Household, members: list[HouseholdMember]) -> dict:
    return {
        "id": household.id,
        "name": household.name,
        "owner_user_id": household.owner_user_id,
        "invite_token": household.invite_token,
        "members": [
            {"user_id": m.user_id, "email": m.user.email, "role": m.role}
            for m in members
        ],
    }


@router.get("")
def list_my_households(db: Session = Depends(get_db), user=Depends(get_current_user)):
    init_db(db)
    memberships = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == user.id)
        .all()
    )
    out = []
    for mem in memberships:
        household = mem.household
        all_members = db.query(HouseholdMember).filter(HouseholdMember.household_id == household.id).all()
        out.append(_household_out(household, all_members))
    return {"results": out}


@router.post("")
def create_household(
    payload: HouseholdIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    init_db(db)
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Household name required")

    household = Household(
        name=payload.name.strip()[:128],
        owner_user_id=user.id,
        invite_token=secrets.token_urlsafe(24),
    )
    db.add(household)
    db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(household)
    members = db.query(HouseholdMember).filter(HouseholdMember.household_id == household.id).all()
    return _household_out(household, members)


@router.post("/join")
def join_household(
    payload: JoinRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    init_db(db)
    household = db.query(Household).filter(Household.invite_token == payload.invite_token).first()
    if household is None:
        raise HTTPException(status_code=404, detail="Invalid invite token")

    existing = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household.id, HouseholdMember.user_id == user.id)
        .first()
    )
    if existing is None:
        db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="member"))
        db.commit()

    members = db.query(HouseholdMember).filter(HouseholdMember.household_id == household.id).all()
    return _household_out(household, members)


@router.post("/{household_id}/rotate-token")
def rotate_invite_token(
    household_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    household = db.query(Household).filter(Household.id == household_id).first()
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    if household.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can rotate the invite token")
    household.invite_token = secrets.token_urlsafe(24)
    db.commit()
    return {"invite_token": household.invite_token}


@router.post("/{household_id}/receipts/{receipt_id}/share")
def share_receipt_to_household(
    household_id: int,
    receipt_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Attach an existing receipt to a household so all members can see it."""
    init_db(db)
    membership = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id, HouseholdMember.user_id == user.id)
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this household")

    receipt = db.query(Receipt).filter(Receipt.id == receipt_id, Receipt.user_id == user.id).first()
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found or not owned by you")
    receipt.household_id = household_id
    db.commit()
    return {"receipt_id": receipt_id, "household_id": household_id}


@router.get("/{household_id}/receipts")
def list_household_receipts(
    household_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """All receipts shared into this household, regardless of original owner."""
    init_db(db)
    membership = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id, HouseholdMember.user_id == user.id)
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this household")

    receipts = (
        db.query(Receipt)
        .filter(Receipt.household_id == household_id)
        .order_by(Receipt.id.desc())
        .limit(200)
        .all()
    )
    out = []
    for r in receipts:
        out.append({
            "id": r.id,
            "owner_user_id": r.user_id,
            "store_name": r.store_name,
            "total_amount": r.total_amount,
            "currency": r.currency,
            "receipt_date": r.receipt_date,
            "processing_status": r.processing_status,
        })
    return {"results": out}


@router.delete("/{household_id}/members/{user_id}")
def remove_member(
    household_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    household = db.query(Household).filter(Household.id == household_id).first()
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    if household.owner_user_id != user.id and user.id != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can remove others")
    membership = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id, HouseholdMember.user_id == user_id)
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Not a member")
    if household.owner_user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove the household owner")
    db.delete(membership)
    db.commit()
    return {"detail": "removed"}
