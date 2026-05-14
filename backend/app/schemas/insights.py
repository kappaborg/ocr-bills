from datetime import datetime
from typing import Any

from pydantic import BaseModel


class InsightOut(BaseModel):
    id: int
    type: str
    message: str
    metadata_json: dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class InsightsListResponse(BaseModel):
    results: list[InsightOut]

