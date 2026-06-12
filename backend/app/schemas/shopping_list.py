from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.recommendations import PriceOption


class ShoppingItemIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(default=1.0, gt=0, le=999)


class ShoppingItemPatch(BaseModel):
    checked: Optional[bool] = None
    quantity: Optional[float] = Field(default=None, gt=0, le=999)


class ShoppingItemOut(BaseModel):
    id: int
    product_name: str
    quantity: float
    checked: bool
    source: str
    created_at: datetime
    price_options: list[PriceOption] = []


class ShoppingListResponse(BaseModel):
    items: list[ShoppingItemOut]
