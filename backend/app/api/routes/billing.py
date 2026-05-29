"""
Billing endpoints — Stripe Checkout, webhook, customer portal, plan/usage status.

Design choices:
  - Hosted Stripe Checkout (not Elements). Fastest to ship, fully PCI-compliant
    out of the box, supports Apple Pay / Google Pay automatically.
  - One Subscription row per user. Webhook is the source of truth for plan +
    period — the checkout success redirect just opens the success page.
  - Endpoints return 503 when STRIPE_SECRET_KEY is unset, so dev environments
    without Stripe still boot cleanly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_db,
    get_user_plan,
    quota_for_plan,
    receipts_in_current_period,
)
from app.core.config import settings
from app.db.models import Plan, ProcessedStripeEvent, Subscription, SubscriptionStatus, User


router = APIRouter()


def _require_stripe():
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Billing is not configured (STRIPE_SECRET_KEY missing). See backend/.env.example.",
        )
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _price_for_plan(plan: str) -> str:
    table = {
        Plan.pro.value:      settings.STRIPE_PRICE_PRO,
        Plan.business.value: settings.STRIPE_PRICE_BUSINESS,
    }
    price_id = table.get(plan)
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe price ID not configured for plan '{plan}'. Set STRIPE_PRICE_{plan.upper()}.",
        )
    return price_id


def _plan_from_price(price_id: str | None) -> str | None:
    if not price_id:
        return None
    if price_id == settings.STRIPE_PRICE_PRO:
        return Plan.pro.value
    if price_id == settings.STRIPE_PRICE_BUSINESS:
        return Plan.business.value
    return None


def _ensure_customer(stripe, user: User, sub: Subscription | None) -> str:
    """Return Stripe customer ID, creating one if needed and stamping it on the Subscription."""
    if sub and sub.stripe_customer_id:
        return sub.stripe_customer_id
    customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
    return customer.id


# ─── Public read endpoints (always available) ──────────────────────────────


@router.get("/plans")
def list_plans():
    """Pricing-page data. No auth, no Stripe key needed."""
    return {
        "currency": "USD",
        "plans": [
            {
                "id": Plan.free.value,
                "name": "Free",
                "price_cents": 0,
                "receipts_per_month": settings.QUOTA_FREE_RECEIPTS_PER_MONTH,
                "features": [
                    "Receipt OCR + confirm flow",
                    "Dashboard + category breakdown",
                    "CSV export",
                    "Full-text search",
                ],
            },
            {
                "id": Plan.pro.value,
                "name": "Pro",
                "price_cents": settings.PRICE_PRO_CENTS,
                "receipts_per_month": settings.QUOTA_PRO_RECEIPTS_PER_MONTH,
                "features": [
                    "Everything in Free",
                    "PDF expense reports",
                    "Monthly budgets",
                    "Recurring-expense detection",
                    "Price-change insights",
                    "Multi-currency display + live FX",
                ],
            },
            {
                "id": Plan.business.value,
                "name": "Business",
                "price_cents": settings.PRICE_BUSINESS_CENTS,
                "receipts_per_month": settings.QUOTA_BUSINESS_RECEIPTS_PER_MONTH or None,
                "features": [
                    "Everything in Pro",
                    "Unlimited receipts",
                    "Household / team sharing",
                    "Bank-statement reconciliation",
                    "Priority Gemini OCR engine",
                ],
            },
        ],
        "configured": bool(settings.STRIPE_SECRET_KEY),
    }


@router.get("/me")
def my_billing(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current plan + quota usage. Drives the dashboard usage bar + settings page."""
    plan = get_user_plan(user, db)
    used = receipts_in_current_period(user, db)
    quota = quota_for_plan(plan)
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    return {
        "plan": plan,
        "status": sub.status if sub else SubscriptionStatus.active.value,
        "current_period_end": sub.current_period_end if sub else None,
        "usage": {
            "receipts_used": used,
            "receipts_quota": quota,           # 0 = unlimited
            "percent": round(used / quota * 100, 1) if quota > 0 else 0.0,
        },
    }


# ─── Stripe-driven endpoints ───────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    plan: str  # "pro" | "business"


@router.post("/checkout")
def create_checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session for the requested plan. Returns the URL to redirect to."""
    stripe = _require_stripe()
    price_id = _price_for_plan(payload.plan)

    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    customer_id = _ensure_customer(stripe, user, sub)

    # Persist the customer ID now so we can correlate the webhook even if the
    # user closes the tab before completing checkout.
    if sub is None:
        sub = Subscription(user_id=user.id, plan=Plan.free.value, stripe_customer_id=customer_id)
        db.add(sub)
    else:
        sub.stripe_customer_id = customer_id
    db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/pricing?canceled=1",
        allow_promotion_codes=True,
        metadata={"user_id": str(user.id), "plan": payload.plan},
    )
    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/portal")
def customer_portal(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stripe-hosted self-service portal (change plan, update card, cancel)."""
    stripe = _require_stripe()
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on file — subscribe first.")

    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/settings",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe → us. Handles subscription lifecycle events. Signature-verified when
    STRIPE_WEBHOOK_SECRET is set (always required in production).
    """
    stripe = _require_stripe()
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        if settings.STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        else:
            # Unsigned-body fallback exists only for local dev runs. In any
            # non-local ENVIRONMENT (e.g. "production" set by fly.toml) the
            # webhook MUST be signature-verified — otherwise anyone hitting
            # /billing/webhook could flip arbitrary users to Business plans.
            if (settings.ENVIRONMENT or "").lower() != "local":
                raise HTTPException(
                    status_code=503,
                    detail="STRIPE_WEBHOOK_SECRET is required outside local dev.",
                )
            import json
            event = json.loads(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook signature verification failed: {e}")

    event_id = event["id"] if isinstance(event, dict) else event.id
    event_type = event["type"] if isinstance(event, dict) else event.type
    data = event["data"]["object"] if isinstance(event, dict) else event.data.object


    # ── Idempotency guard ──────────────────────────────────────────────────
    # Stripe retries on 5xx and on timeout; without this check a retried
    # `customer.subscription.updated` would re-sync state and a retried
    # `checkout.session.completed` would issue a second Stripe API call.
    if event_id:
        seen = db.query(ProcessedStripeEvent).filter(ProcessedStripeEvent.event_id == event_id).first()
        if seen is not None:
            return {"received": True, "already_processed": True, "event_id": event_id}
        db.add(ProcessedStripeEvent(event_id=event_id, event_type=event_type or ""))
        db.commit()

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        _sync_subscription_from_stripe(db, data)
    elif event_type == "customer.subscription.deleted":
        _mark_canceled(db, data)
    elif event_type == "checkout.session.completed":
        # First-time conversion — pull the subscription object Stripe just created.
        sub_id = data.get("subscription") if isinstance(data, dict) else data.subscription
        if sub_id:
            full_sub = stripe.Subscription.retrieve(sub_id)
            _sync_subscription_from_stripe(db, full_sub)

    return {"received": True}


def _sync_subscription_from_stripe(db: Session, stripe_sub) -> None:
    """Upsert our Subscription row from a Stripe subscription payload."""
    # Stripe SDK objects + dicts both supported.
    def g(key, default=None):
        if isinstance(stripe_sub, dict):
            return stripe_sub.get(key, default)
        return getattr(stripe_sub, key, default)

    customer_id = g("customer")
    stripe_sub_id = g("id")
    status = g("status") or "active"
    period_end_ts = g("current_period_end")

    items = g("items") or {}
    if isinstance(items, dict):
        data_list = items.get("data") or []
    else:
        data_list = getattr(items, "data", []) or []
    price_id = None
    if data_list:
        first = data_list[0]
        price = first.get("price") if isinstance(first, dict) else getattr(first, "price", None)
        if price is not None:
            price_id = price.get("id") if isinstance(price, dict) else getattr(price, "id", None)

    plan = _plan_from_price(price_id) or Plan.free.value

    sub = db.query(Subscription).filter(Subscription.stripe_customer_id == customer_id).first()
    if sub is None:
        # Race with checkout: webhook fired before we wrote the customer row. Find by stripe_sub_id.
        sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if sub is None:
        # No Subscription row yet at all. Lookup user via Stripe customer metadata.
        import stripe as stripe_mod
        stripe_mod.api_key = settings.STRIPE_SECRET_KEY
        customer = stripe_mod.Customer.retrieve(customer_id)
        user_id_meta = (customer.metadata or {}).get("user_id")
        if not user_id_meta:
            return
        sub = Subscription(user_id=int(user_id_meta))
        db.add(sub)

    sub.stripe_customer_id = customer_id
    sub.stripe_subscription_id = stripe_sub_id
    sub.plan = plan
    sub.status = status
    sub.current_period_end = (
        datetime.fromtimestamp(int(period_end_ts), tz=timezone.utc).replace(tzinfo=None)
        if period_end_ts else None
    )
    sub.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


def _mark_canceled(db: Session, stripe_sub) -> None:
    stripe_sub_id = stripe_sub.get("id") if isinstance(stripe_sub, dict) else stripe_sub.id
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if sub:
        sub.status = SubscriptionStatus.canceled.value
        sub.plan = Plan.free.value
        sub.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
