from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReceiptItemOut(BaseModel):
    id: int
    item_name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    item_price: float
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    confidence_score: float = 0.0

    class Config:
        from_attributes = True


class ReceiptOut(BaseModel):
    id: int
    processing_status: str
    processing_error: Optional[str] = None

    raw_text: Optional[str] = None
    detected_language: Optional[str] = None
    receipt_date: Optional[datetime] = None
    store_name: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    tax_amount: Optional[float] = None

    items: list[ReceiptItemOut] = []

    class Config:
        from_attributes = True


class ReceiptUploadResult(BaseModel):
    receipt_id: int
    processing_status: str


class ReceiptUploadResponse(BaseModel):
    results: list[ReceiptUploadResult]


class ReceiptConfirmItemIn(BaseModel):
    id: Optional[int] = None
    item_name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    item_price: float
    category_id: Optional[int] = None


class ReceiptConfirmRequest(BaseModel):
    items: list[ReceiptConfirmItemIn]

