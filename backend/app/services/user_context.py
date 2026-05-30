"""
Per-user OCR context — what we know about this user that can disambiguate
otherwise-ambiguous receipts.

We pull a compact summary from their last 50 confirmed receipts: which stores
they shop at, which currencies show up, what language their receipts are in,
and which categories they actually use. Engines that support natural-language
prompts (Gemini, Claude) can paste this in to nudge the model toward the
user's reality without hard-coding it.

Cached per-user with a short TTL so a busy uploader doesn't trigger one DB
query per receipt.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Receipt, ReceiptItem, Category, ReceiptStatus


@dataclass
class UserContext:
    """Lightweight per-user signal used to bias the OCR engine."""

    user_id: int
    common_stores: list[str] = field(default_factory=list)        # top ~8 by frequency
    common_currencies: list[str] = field(default_factory=list)    # top ~4
    primary_language: Optional[str] = None                        # most-frequent detected_language
    common_categories: list[str] = field(default_factory=list)    # categories with ≥1 line item

    def is_meaningful(self) -> bool:
        """Skip prompt-injection when we don't actually know anything yet."""
        return bool(self.common_stores or self.common_currencies or self.primary_language)


# ── In-memory cache ──────────────────────────────────────────────────────
# Single-process; fine for the current scale-to-one deployment. For multi-
# worker prod, swap for Redis. Cache window matches typical bulk-upload
# sessions (a few minutes) so all receipts in one batch share one DB read.
_CACHE_TTL_SECONDS = 5 * 60
_cache: dict[int, tuple[float, UserContext]] = {}


def invalidate(user_id: int) -> None:
    """Drop cached context — call after a confirm so subsequent uploads use
    fresh history. Safe no-op if nothing was cached."""
    _cache.pop(user_id, None)


def build_user_context(user_id: int, db: Session) -> UserContext:
    """Look up cached, otherwise compute from DB. Returns an empty-but-valid
    UserContext for users with no history (don't break the prompt)."""
    now = time.time()
    cached = _cache.get(user_id)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    ctx = _compute(user_id, db)
    _cache[user_id] = (now, ctx)
    return ctx


def _compute(user_id: int, db: Session) -> UserContext:
    """Pull the last 50 confirmed receipts and derive a UserContext from them."""
    receipts = (
        db.query(Receipt)
        .filter(Receipt.user_id == user_id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .order_by(Receipt.id.desc())
        .limit(50)
        .all()
    )

    store_counter: Counter[str] = Counter()
    currency_counter: Counter[str] = Counter()
    lang_counter: Counter[str] = Counter()
    for r in receipts:
        if r.store_name:
            # Strip the "Sample — " prefix from sample receipts so we don't
            # tell Gemini the user shops at "Sample — Konzum".
            name = r.store_name
            if name.startswith("Sample — "):
                name = name[len("Sample — "):]
            store_counter[name] += 1
        if r.currency:
            currency_counter[r.currency] += 1
        if r.detected_language:
            lang_counter[r.detected_language] += 1

    # Categories the user has actually used (had ≥1 receipt item categorized)
    # in their last 50 receipts. Joined separately for clarity.
    cat_rows = (
        db.query(Category.name)
        .join(ReceiptItem, ReceiptItem.category_id == Category.id)
        .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
        .filter(Receipt.user_id == user_id)
        .filter(Receipt.processing_status == ReceiptStatus.confirmed.value)
        .distinct()
        .limit(20)
        .all()
    )
    common_categories = sorted({row[0] for row in cat_rows if row[0]})

    return UserContext(
        user_id=user_id,
        common_stores=[s for s, _ in store_counter.most_common(8)],
        common_currencies=[c for c, _ in currency_counter.most_common(4)],
        primary_language=(lang_counter.most_common(1)[0][0] if lang_counter else None),
        common_categories=common_categories,
    )
