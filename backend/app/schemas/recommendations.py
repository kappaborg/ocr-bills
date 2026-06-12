from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PriceAction(BaseModel):
    """Where tapping this price chip lands the user. type: maps | glovo |
    wolt | shop. maps is always constructible; the rest come from the
    hand-curated store_links table."""
    type: str
    url: str


class PriceOption(BaseModel):
    """One store's current price for a product, from the anonymous
    crowdsourced observation feed. Provenance booleans are resolved
    server-side via internal lineage — identities never leave the DB."""
    store: str
    store_display: str
    price: float
    currency: str
    observed_at: datetime
    staleness_days: int
    observation_count: int = 1
    is_own: bool = False
    verified: bool = False
    action: PriceAction | None = None


class NeedToBuyItem(BaseModel):
    product_id: int
    product_name: str
    category_name: Optional[str] = None
    last_purchased_at: Optional[datetime] = None
    next_expected_buy_date: Optional[datetime] = None
    score: float
    price_options: list[PriceOption] = []


class NeedToBuyResponse(BaseModel):
    results: list[NeedToBuyItem]

