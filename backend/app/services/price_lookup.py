"""
Read-side of the crowdsourced price feed: best current price per store
for a product, with staleness decay and outlier rejection.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy.orm import Session

from app.db.models import PriceObservation

# Observations older than this carry no signal (prices drift, promos end).
_MAX_AGE_DAYS = 45
# Within the window, the median is computed over the most recent slice.
_MEDIAN_WINDOW_DAYS = 30


def price_options_for(
    product_normalized: str,
    db: Session,
    *,
    top: int = 3,
) -> list[dict]:
    """
    Top stores for a product by freshest median price.

    Returns [{store, store_display, price, currency, observed_at,
    staleness_days}] sorted by price ascending. Observations are grouped
    per (store, currency) — cross-currency comparison is intentionally
    NOT attempted in v1.
    """
    if not product_normalized:
        return []

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    floor = now - timedelta(days=_MAX_AGE_DAYS)

    rows = (
        db.query(PriceObservation)
        .filter(PriceObservation.product_normalized == product_normalized)
        .filter(PriceObservation.observed_at >= floor)
        .order_by(PriceObservation.observed_at.desc())
        .limit(500)
        .all()
    )
    if not rows:
        return []

    # Outlier rejection: drop anything beyond 3× the store's median — the
    # same ratio approach insights.py uses for total-amount anomalies.
    by_store: dict[tuple[str, str], list[PriceObservation]] = defaultdict(list)
    for o in rows:
        by_store[(o.store_normalized, o.currency)].append(o)

    options: list[dict] = []
    median_floor = now - timedelta(days=_MEDIAN_WINDOW_DAYS)
    for (store_key, currency), obs in by_store.items():
        # Outlier anchor: the median of the LOWER half of prices. A plain
        # median fails on tiny samples — with [2.55, 24.00] the outlier
        # drags its own threshold up (median 13.28 × 3 = 39.8) and survives.
        # The lower-half median stays at 2.55 and rejects 24.00 cleanly,
        # while legitimate price rises (≤3×) still pass.
        prices = sorted(o.price for o in obs)
        lower_half = prices[: max(1, (len(prices) + 1) // 2)]
        anchor = median(lower_half)
        clean = [o for o in obs if o.price <= anchor * 3]
        if not clean:
            continue
        recent = [o for o in clean if o.observed_at >= median_floor] or clean
        price = round(median(o.price for o in recent), 2)
        freshest = max(o.observed_at for o in recent)
        options.append({
            "store": store_key,
            "store_display": recent[0].store_display,
            "price": price,
            "currency": currency,
            "observed_at": freshest,
            "staleness_days": max(0, int((now - freshest).total_seconds() // 86400)),
        })

    options.sort(key=lambda o: o["price"])
    return options[:top]
