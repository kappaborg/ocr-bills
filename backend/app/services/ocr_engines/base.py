"""
OCR engine contract.

Every engine returns an OCRResult. Two flavors are supported:

  1. Raw-text path (e.g. Tesseract): set `raw_text` only and let the
     downstream regex parser extract structured fields.
  2. Structured path (e.g. Gemini, Claude, Mindee): set both `raw_text`
     and `structured` so the receipt-processing pipeline can skip the
     regex parser entirely.

This split lets cheap local OCR coexist with high-accuracy VLMs that
already understand receipt semantics.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.user_context import UserContext


@dataclass
class StructuredItem:
    item_name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    item_price: float = 0.0


@dataclass
class StructuredReceipt:
    store_name: Optional[str] = None
    receipt_date: Optional[datetime] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    detected_language: Optional[str] = None
    items: list[StructuredItem] = field(default_factory=list)


@dataclass
class OCRResult:
    raw_text: str
    structured: Optional[StructuredReceipt] = None
    # 0.0 – 1.0. Engines that can't measure confidence default to 0.5.
    confidence: float = 0.5
    engine: str = ""


class OCREngine(ABC):
    """Implement `extract` in subclasses and register the engine in `ocr.py`."""

    name: str = "base"

    @abstractmethod
    def extract(self, file_path: str, context: "Optional[UserContext]" = None) -> OCRResult:
        """Run OCR on a single image file and return text (+ optional structured fields).

        `context` is an optional UserContext (per-user history summary). Engines
        that support natural-language prompts (Gemini, Claude) can use it to
        disambiguate edge cases — common stores, currencies, language, etc.
        Regex-based engines (Tesseract) can ignore it.
        """
        ...
