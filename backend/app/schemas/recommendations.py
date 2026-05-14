from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NeedToBuyItem(BaseModel):
    product_id: int
    product_name: str
    category_name: Optional[str] = None
    last_purchased_at: Optional[datetime] = None
    next_expected_buy_date: Optional[datetime] = None
    score: float


class NeedToBuyResponse(BaseModel):
    results: list[NeedToBuyItem]

