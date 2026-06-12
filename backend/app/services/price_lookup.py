"""
Read-side of the crowdsourced price feed: best current price per store
for a product, with staleness decay, outlier rejection, and provenance
(observation count / own-vs-community / verified) resolved through the
internal receipt lineage without ever exposing user identity.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.db.models import PriceObservation, Receipt, ReceiptItem

# Observations older than this carry no signal (prices drift, promos end).
_MAX_AGE_DAYS = 45
# Within the window, the median is computed over the most recent slice.
_MEDIAN_WINDOW_DAYS = 30


def _maps_action(store_display: str) -> dict:
    """Universal fallback action: a Google Maps search for the store.
    Always constructible; opens the Maps app on Android, browser/Maps on
    iOS, a new tab on web. quote_plus handles Cyrillic/Arabic names."""
    return {
        "type": "maps",
        "url": "https://www.google.com/maps/search/?api=1&query=" + quote_plus(store_display),
    }


def _resolve_action(store_key: str, store_display: str, db: Session) -> dict:
    """Pick the best landing for a store: curated delivery/shop link when
    one exists, otherwise maps search. Curated URLs are hand-verified —
    a broken deep link is worse than the maps fallback."""
    from app.db.models import StoreLink

    link = db.query(StoreLink).filter(StoreLink.store_normalized == store_key).first()
    if link is not None:
        for kind, url in (("glovo", link.glovo_url), ("wolt", link.wolt_url), ("shop", link.shop_url)):
            if url:
                return {"type": kind, "url": url}
        if link.maps_query:
            return _maps_action(link.maps_query)
    return _maps_action(store_display)


def price_options_for(
    product_normalized: str,
    db: Session,
    *,
    top: int = 3,
    requesting_user_id: int | None = None,
) -> list[dict]:
    """
    Top stores for a product by freshest median price.

    Returns [{store, store_display, price, currency, observed_at,
    staleness_days, observation_count, is_own, verified, action}] sorted
    by price ascending. Observations are grouped per (store, currency) —
    cross-currency comparison is intentionally NOT attempted in v1.

    Provenance is resolved through receipt_item lineage strictly
    server-side: the API exposes booleans, never identities.
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

    # Resolve lineage once for all observations: item_id → (receipt_id,
    # user_id). GDPR-deleted lineage (NULL receipt_item_id) simply doesn't
    # contribute to is_own/verified.
    item_ids = [o.receipt_item_id for o in rows if o.receipt_item_id is not None]
    lineage: dict[int, tuple[int, int]] = {}
    if item_ids:
        pairs = (
            db.query(ReceiptItem.id, Receipt.id, Receipt.user_id)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .filter(ReceiptItem.id.in_(item_ids))
            .all()
        )
        lineage = {item_id: (receipt_id, user_id) for item_id, receipt_id, user_id in pairs}

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

        receipt_ids = {lineage[o.receipt_item_id][0] for o in clean
                       if o.receipt_item_id in lineage}
        is_own = (
            requesting_user_id is not None
            and any(lineage.get(o.receipt_item_id, (None, None))[1] == requesting_user_id
                    for o in clean if o.receipt_item_id is not None)
        )
        verified = len(clean) >= 3 and len(receipt_ids) >= 2

        options.append({
            "store": store_key,
            "store_display": recent[0].store_display,
            "price": price,
            "currency": currency,
            "observed_at": freshest,
            "staleness_days": max(0, int((now - freshest).total_seconds() // 86400)),
            "observation_count": len(clean),
            "is_own": is_own,
            "verified": verified,
            "action": _resolve_action(store_key, recent[0].store_display, db),
        })

    options.sort(key=lambda o: o["price"])
    return options[:top]
