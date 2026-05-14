from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TransactionOut(BaseModel):
    id: int  # receipt_item id
    receipt_id: int
    date: Optional[datetime] = None
    store_name: Optional[str] = None
    item_name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    item_price: float
    category_name: Optional[str] = None

    class Config:
        from_attributes = True


class TransactionsListResponse(BaseModel):
    results: list[TransactionOut]

