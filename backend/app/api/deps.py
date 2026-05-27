from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Plan, Receipt, Subscription, SubscriptionStatus, User
from app.db.session import SessionLocal
from app.utils.auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


_PLAN_RANK: dict[str, int] = {
    Plan.free.value:     0,
    Plan.pro.value:      1,
    Plan.business.value: 2,
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except Exception:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_exception
    return user


# ── Billing / quota helpers ────────────────────────────────────────────────


def _is_active(sub: Subscription | None) -> bool:
    """Subscription is active when status is active/trialing and the period hasn't lapsed."""
    if sub is None:
        return False
    if sub.status not in (SubscriptionStatus.active.value, SubscriptionStatus.trialing.value):
        return False
    if sub.current_period_end is None:
        return True
    return sub.current_period_end > datetime.now(timezone.utc).replace(tzinfo=None)


def get_user_plan(user: User, db: Session) -> str:
    """Return the user's active plan name, falling back to 'free'."""
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if _is_active(sub):
        return sub.plan
    return Plan.free.value


def quota_for_plan(plan: str) -> int:
    """Receipt quota per period for a given plan. 0 means unlimited."""
    return {
        Plan.free.value:     settings.QUOTA_FREE_RECEIPTS_PER_MONTH,
        Plan.pro.value:      settings.QUOTA_PRO_RECEIPTS_PER_MONTH,
        Plan.business.value: settings.QUOTA_BUSINESS_RECEIPTS_PER_MONTH,
    }.get(plan, settings.QUOTA_FREE_RECEIPTS_PER_MONTH)


def _period_start(now: datetime) -> datetime:
    """Start of the current calendar month — used as the quota window when the user
    has no Stripe subscription (free tier) or the subscription has no period_end yet."""
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def receipts_in_current_period(user: User, db: Session) -> int:
    """Count receipts uploaded by the user inside the current billing period."""
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if _is_active(sub) and sub.current_period_end is not None:
        # Roll back one period from the end to find this period's start.
        # Stripe sends 1-month windows; one-month subtraction is fine for the
        # SaaS use case (edge: leap years near Feb-end). For year subscriptions,
        # we'd flip this to a 12-month window — out of scope for v1.
        start = sub.current_period_end - timedelta(days=31)
    else:
        start = _period_start(now)
    return (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id, Receipt.created_at >= start)
        .count()
    )


def _err_402(detail: str, plan_required: str | None = None) -> HTTPException:
    headers = {"X-Upgrade-Required": plan_required} if plan_required else None
    return HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail, headers=headers)


def enforce_quota(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Dependency for receipt-creation endpoints. Raises 402 when the user hits the cap."""
    plan = get_user_plan(user, db)
    quota = quota_for_plan(plan)
    if quota == 0:
        return  # unlimited
    used = receipts_in_current_period(user, db)
    if used >= quota:
        raise _err_402(
            f"Receipt limit reached ({used}/{quota} this period on the {plan} plan). "
            f"Upgrade for more.",
            plan_required="pro" if plan == Plan.free.value else "business",
        )


def require_plan(min_plan: str):
    """Dependency factory: gate an endpoint behind a minimum plan tier."""
    if min_plan not in _PLAN_RANK:
        raise ValueError(f"Unknown plan: {min_plan}")

    def _checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        plan = get_user_plan(user, db)
        if _PLAN_RANK[plan] < _PLAN_RANK[min_plan]:
            raise _err_402(
                f"This feature requires the {min_plan} plan (you're on {plan}).",
                plan_required=min_plan,
            )
        return user

    return _checker
