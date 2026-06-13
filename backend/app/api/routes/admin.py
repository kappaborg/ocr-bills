"""
Admin endpoints called by external cron (GitHub Actions). Guarded by
the ADMIN_TOKEN shared secret — never expose without it.
"""
import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import User
from app.services.weekly_summary import build_summary, render_html, send_via_resend

router = APIRouter()


def _require_admin(x_admin_token: str = Header(...)) -> None:
    """Constant-time comparison. ADMIN_TOKEN must be set to use these
    endpoints; an empty config rejects everything."""
    expected = settings.ADMIN_TOKEN or ""
    if not expected or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Forbidden")


def _unsubscribe_token(user_id: int) -> str:
    """Per-user signed token. Anyone with this token can unsubscribe that
    user — but never authenticate as them. Stable across emails so users
    can always click any past email to opt out."""
    secret = settings.JWT_SECRET.encode("utf-8")
    payload = f"unsub:{user_id}".encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()[:32]


def _verify_unsubscribe_token(user_id: int, token: str) -> bool:
    return hmac.compare_digest(_unsubscribe_token(user_id), token)


@router.post("/send-weekly-summaries")
def send_weekly_summaries(
    _admin=Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Build + send a weekly summary to every opted-in user who has at
    least one confirmed receipt this week. Idempotent within a single
    day: weekly_summary_last_sent_at gates re-runs."""
    if not settings.RESEND_API_KEY:
        return {"sent": 0, "skipped": 0, "reason": "RESEND_API_KEY not set"}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    users = (
        db.query(User)
        .filter(User.weekly_summary_unsubscribed.is_(False))
        .all()
    )

    base_url = (settings.FRONTEND_URL or "").rstrip("/")
    sent, skipped, failed = 0, 0, 0
    for u in users:
        if u.weekly_summary_last_sent_at and u.weekly_summary_last_sent_at >= today_midnight:
            skipped += 1
            continue
        summary = build_summary(u, db)
        if not summary.has_content:
            skipped += 1
            continue

        unsub_url = f"{base_url}/unsubscribe?u={u.id}&t={_unsubscribe_token(u.id)}"
        html = render_html(
            summary,
            user_email=u.email,
            unsubscribe_url=unsub_url,
            dashboard_url=f"{base_url}/dashboard",
        )
        ok = send_via_resend(
            to=u.email,
            subject=f"Your week: {summary.total_week:.2f} {summary.currency}",
            html=html,
        )
        if ok:
            u.weekly_summary_last_sent_at = now
            sent += 1
        else:
            failed += 1

    db.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed}


@router.get("/unsubscribe-status/{user_id}")
def unsubscribe_status(
    user_id: int,
    t: str,
    db: Session = Depends(get_db),
):
    """Token-gated read of opt-out state. Used by the public
    /unsubscribe page to confirm the action before mutating."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not _verify_unsubscribe_token(user_id, t):
        raise HTTPException(status_code=404)
    return {"email": user.email, "unsubscribed": user.weekly_summary_unsubscribed}


@router.post("/unsubscribe/{user_id}")
def unsubscribe(
    user_id: int,
    t: str,
    db: Session = Depends(get_db),
):
    """Flip the opt-out flag. Idempotent."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not _verify_unsubscribe_token(user_id, t):
        raise HTTPException(status_code=404)
    user.weekly_summary_unsubscribed = True
    db.commit()
    return {"ok": True}
