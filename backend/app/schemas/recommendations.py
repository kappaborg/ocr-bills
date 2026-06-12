from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PriceOption(BaseModel):
    """One store's current price for a product, from the anonymous
    crowdsourced observation feed."""
    store: str
    store_display: str
    price: float
    currency: str
    observed_at: datetime
    staleness_days: int


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

