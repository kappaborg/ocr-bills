"""
Personalized weekly summary email.

Composes the data the user already produced — last 7 days of confirmed
receipts, top category, comparison vs the prior week, and one Market
Pulse nudge ("you bought milk twice this week; Bingo had it 8% cheaper
on Monday than the avg") — into a single short HTML email.

Designed for retention: the email arrives Monday morning whether the
user opened the app or not. Built on the existing insights/price feed
so no new data sources.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    InventoryItem,
    PriceObservation,
    Product,
    Receipt,
    ReceiptItem,
    ReceiptStatus,
    User,
)


@dataclass
class WeeklySummary:
    """Pure data — the renderer turns this into HTML."""
    total_week: float
    total_prior_week: float
    currency: str
    receipt_count: int
    top_category: Optional[str]
    top_category_amount: float
    price_nudge: Optional[str]  # One-sentence Market Pulse hint, e.g. "Coffee was 8% cheaper at Bingo this week"

    @property
    def has_content(self) -> bool:
        return self.receipt_count > 0


def _effective_date_column():
    """Coalesce receipt_date (Gemini may have failed to parse it) with
    created_at. Same pattern insights.py uses."""
    return func.coalesce(Receipt.receipt_date, Receipt.created_at)


def build_summary(user: User, db: Session) -> WeeklySummary:
    """Build the summary data block. Currency follows the user's most
    common confirmed-receipt currency in the last 30 days."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    week_start = now - timedelta(days=7)
    prior_week_start = now - timedelta(days=14)
    effective_date = _effective_date_column()

    base = (
        db.query(func.sum(ReceiptItem.item_price))
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
    )
    total_week = float(base.filter(effective_date >= week_start).scalar() or 0.0)
    total_prior_week = float(
        base.filter(effective_date >= prior_week_start, effective_date < week_start).scalar() or 0.0
    )

    # Currency: most common in last 30 days, defaults to BAM for ex-YU bias
    ccy_rows = (
        db.query(Receipt.currency, func.count(Receipt.id))
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(effective_date >= now - timedelta(days=30))
        .group_by(Receipt.currency)
        .order_by(func.count(Receipt.id).desc())
        .all()
    )
    currency = (ccy_rows[0][0] if ccy_rows and ccy_rows[0][0] else "BAM")

    receipt_count = (
        db.query(func.count(Receipt.id))
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(effective_date >= week_start)
        .scalar() or 0
    )

    # Top category — by sum of item_price this week.
    from app.db.models import Category
    cat_rows = (
        db.query(Category.name, func.sum(ReceiptItem.item_price))
        .join(ReceiptItem, ReceiptItem.category_id == Category.id)
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .filter(Receipt.user_id == user.id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(effective_date >= week_start)
        .group_by(Category.name)
        .order_by(func.sum(ReceiptItem.item_price).desc())
        .limit(1)
        .all()
    )
    top_category, top_category_amount = (cat_rows[0] if cat_rows else (None, 0.0))

    # Market Pulse nudge: a recurring item the user bought this week that
    # had a cheaper price option elsewhere. One sentence max.
    price_nudge = _build_price_nudge(user.id, week_start, db, currency)

    return WeeklySummary(
        total_week=round(total_week, 2),
        total_prior_week=round(total_prior_week, 2),
        currency=currency,
        receipt_count=int(receipt_count),
        top_category=top_category,
        top_category_amount=round(float(top_category_amount or 0), 2),
        price_nudge=price_nudge,
    )


def _build_price_nudge(user_id: int, week_start: datetime, db: Session, currency: str) -> Optional[str]:
    """Find ONE product the user paid for this week that other stores
    sold cheaper. Returns a single user-facing sentence or None."""
    from app.services.product_normalization import normalize_product_name

    # User's purchases this week with their paid prices, grouped by product.
    rows = (
        db.query(ReceiptItem.item_name, ReceiptItem.item_price, Receipt.store_name)
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .filter(Receipt.user_id == user_id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .filter(Receipt.currency == currency)
        .filter(func.coalesce(Receipt.receipt_date, Receipt.created_at) >= week_start)
        .all()
    )
    if not rows:
        return None

    purchases: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for name, price, store in rows:
        norm = normalize_product_name(name)
        if not norm or not price or price <= 0:
            continue
        purchases[norm].append((float(price), store or "your store"))

    best: Optional[tuple[float, str, float, float, str]] = None  # (saving_pct, display_name, paid, alt_price, alt_store)
    for norm, paid_list in purchases.items():
        paid = median(p for p, _ in paid_list)
        # Compare to the cheapest 30-day community price elsewhere.
        obs = (
            db.query(PriceObservation)
            .filter(PriceObservation.product_normalized == norm)
            .filter(PriceObservation.currency == currency)
            .filter(PriceObservation.observed_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30))
            .all()
        )
        if not obs:
            continue
        by_store: dict[str, list[float]] = defaultdict(list)
        for o in obs:
            by_store[o.store_display].append(o.price)
        # Exclude the store the user actually used (no point telling them they could've bought
        # the same thing at the same place).
        their_stores = {s for _, s in paid_list}
        cheaper = []
        for store, prices in by_store.items():
            if store in their_stores:
                continue
            med = median(prices)
            if med < paid:
                cheaper.append((med, store))
        if not cheaper:
            continue
        cheaper.sort(key=lambda x: x[0])
        alt_price, alt_store = cheaper[0]
        saving_pct = (paid - alt_price) / paid * 100
        if saving_pct < 8:
            continue
        # Use the user's printed product name (paid_list keeps it).
        display_name = paid_list[0][0:1] and paid_list[0][1]  # placeholder — name reconstruction below
        # Recover a display name from the original rows.
        display_name = next((r[0] for r in rows if normalize_product_name(r[0]) == norm), norm)
        if best is None or saving_pct > best[0]:
            best = (saving_pct, display_name, paid, alt_price, alt_store)

    if best is None:
        return None
    saving_pct, display_name, paid, alt_price, alt_store = best
    return (
        f"You paid {paid:.2f} {currency} for {display_name} this week — "
        f"{alt_store} had it for {alt_price:.2f} ({saving_pct:.0f}% less)."
    )


def render_html(summary: WeeklySummary, *, user_email: str, unsubscribe_url: str, dashboard_url: str) -> str:
    """Render the data block to an inline-styled HTML email.

    Inline styles only — Gmail and friends strip <style> blocks. Layout
    keeps to a single column max 540px so it works in narrow mail clients.
    """
    delta = summary.total_week - summary.total_prior_week
    delta_sign = "+" if delta >= 0 else "−"
    delta_color = "#F87171" if delta > 0 else "#34D399"
    delta_pct = abs(delta) / summary.total_prior_week * 100 if summary.total_prior_week > 0 else 0

    delta_line = (
        f'<span style="color:{delta_color};font-weight:600;">'
        f'{delta_sign}{abs(delta):.2f} {summary.currency}'
        f'{f" ({delta_pct:.0f}% vs last week)" if summary.total_prior_week > 0 else ""}'
        f'</span>'
        if summary.total_prior_week > 0
        else '<span style="color:#94A3B8;">First full week — we\'ll have a comparison next Monday.</span>'
    )

    top_category_block = (
        f'<tr><td style="padding:8px 0;color:#94A3B8;font-size:13px;">Top category</td>'
        f'<td style="padding:8px 0;text-align:right;color:#F1F5F9;font-size:13px;font-weight:600;">'
        f'{summary.top_category} · {summary.top_category_amount:.2f} {summary.currency}</td></tr>'
        if summary.top_category else ''
    )
    nudge_block = (
        f'<div style="margin-top:24px;padding:16px 18px;background:#0F172A;border:1px solid #1E293B;border-radius:12px;">'
        f'<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#22D3EE;font-weight:600;margin-bottom:6px;">Market Pulse</div>'
        f'<div style="font-size:14px;color:#F1F5F9;line-height:1.5;">{summary.price_nudge}</div>'
        f'</div>'
        if summary.price_nudge else ''
    )

    return f"""\
<!doctype html>
<html><body style="margin:0;padding:0;background:#020617;color:#F1F5F9;font-family:-apple-system,Segoe UI,Roboto,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#020617;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="540" cellspacing="0" cellpadding="0" border="0" style="max-width:540px;width:100%;">
        <tr><td style="padding-bottom:24px;">
          <span style="display:inline-block;width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#22D3EE,#34D399);color:#020617;font-weight:700;text-align:center;line-height:32px;vertical-align:middle;">◈</span>
          <span style="font-size:18px;font-weight:600;color:#F1F5F9;margin-left:10px;vertical-align:middle;">Ex<span style="color:#22D3EE;">TaSy</span></span>
        </td></tr>
        <tr><td style="padding-bottom:8px;">
          <p style="margin:0;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:rgba(34,211,238,0.9);font-weight:600;">Your week</p>
        </td></tr>
        <tr><td>
          <h1 style="margin:0;font-size:26px;font-weight:700;color:#F1F5F9;letter-spacing:-0.5px;">Spending pulse</h1>
        </td></tr>
        <tr><td style="padding-top:24px;">
          <div style="padding:20px;background:#0F172A;border:1px solid #1E293B;border-radius:14px;">
            <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#94A3B8;font-weight:600;">Total this week</div>
            <div style="margin-top:6px;font-family:'SF Mono',Menlo,monospace;font-size:32px;font-weight:700;color:#F1F5F9;">
              {summary.total_week:.2f} <span style="color:#94A3B8;font-weight:500;">{summary.currency}</span>
            </div>
            <div style="margin-top:6px;font-size:13px;">{delta_line}</div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:16px;">
              <tr><td style="padding:8px 0;color:#94A3B8;font-size:13px;">Receipts</td>
                  <td style="padding:8px 0;text-align:right;color:#F1F5F9;font-size:13px;font-weight:600;">{summary.receipt_count}</td></tr>
              {top_category_block}
            </table>
          </div>
        </td></tr>
        <tr><td>{nudge_block}</td></tr>
        <tr><td style="padding-top:28px;">
          <a href="{dashboard_url}" style="display:inline-block;padding:12px 22px;background:linear-gradient(90deg,#06B6D4,#10B981);color:#020617;font-weight:700;font-size:14px;text-decoration:none;border-radius:12px;">Open dashboard</a>
        </td></tr>
        <tr><td style="padding-top:40px;border-top:1px solid #1E293B;margin-top:32px;">
          <p style="font-size:11px;color:#64748B;line-height:1.6;margin:24px 0 0;">
            You're receiving this because you signed up for ExTaSy with {user_email}.
            <a href="{unsubscribe_url}" style="color:#94A3B8;">Unsubscribe</a> from these weekly emails.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""


def send_via_resend(*, to: str, subject: str, html: str) -> bool:
    """Best-effort send via Resend's HTTP API. Returns True on 2xx.
    No-op when RESEND_API_KEY is empty — useful for local dev."""
    if not settings.RESEND_API_KEY:
        return False
    try:
        import urllib.request
        import json as _json

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=_json.dumps({
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
