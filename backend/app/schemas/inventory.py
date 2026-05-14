from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InventoryItemOut(BaseModel):
    product_id: int
    product_name: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None

    last_purchased_at: Optional[datetime] = None
    purchase_count: int = 0
    avg_interval_days: Optional[float] = None
    next_expected_buy_date: Optional[datetime] = None


class InventoryListResponse(BaseModel):
    results: list[InventoryItemOut]

