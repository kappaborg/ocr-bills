"""
Gemini vision engine.

Sends a single image + a tightly-scoped prompt to Gemini and asks for a
structured JSON response describing the receipt. Multi-language native
(Latin, Cyrillic, Arabic, CJK, Devanagari, Thai, Hebrew, Greek, …) with no
preprocessing required.

Free tier: 1500 requests/day on gemini-2.5-flash. Get a key from
https://aistudio.google.com/app/apikey and set GEMINI_API_KEY in backend/.env.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.services.ocr_engines.base import OCREngine, OCRResult, StructuredItem, StructuredReceipt


_DEFAULT_MODEL = "gemini-2.5-flash"

_PROMPT = """\
You are extracting structured data from a receipt photo. Return JSON only
matching the schema. Read the receipt carefully even if it is in Bosnian,
Serbian, Croatian, Russian, Arabic, German, Turkish, Japanese, Chinese, Korean,
or any other language/script.

Rules:
- store_name: the merchant/business name from the top of the receipt
- receipt_date: ISO 8601 date or datetime if printed; null if not visible
- currency: 3-letter ISO 4217 code (USD, EUR, BAM, RUB, SAR, JPY, TRY, RSD,
  HRK, AED, GBP, …). Infer from currency symbol, language, or country context
  if not explicitly printed. Use BAM (Bosnian convertible mark) for KM.
- total_amount: the final total customer paid (NOT subtotal)
- tax_amount: VAT/PDV/MWST amount paid; null if not printed
- items: each line item as {item_name, quantity, unit_price, item_price}.
  If quantity is implied as 1, return 1. unit_price is per unit. item_price
  is the line total. Skip tax lines, totals, fiscal IDs, dates, payment lines.
- detected_language: BCP-47 language tag of the receipt text (bs, sr, hr,
  ru, ar, de, tr, ja, zh, ko, en, …)
- raw_text: a verbatim transcription of every legible word on the receipt,
  preserving line breaks

Be conservative: if a field is unclear, use null. Do not invent data."""


_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        # google-genai uses Google's Schema proto, not JSON Schema. Union
        # types ("string" | "null") aren't supported — use nullable: True.
        "store_name":        {"type": "string", "nullable": True},
        "receipt_date":      {"type": "string", "nullable": True},
        "currency":          {"type": "string", "nullable": True},
        "total_amount":      {"type": "number", "nullable": True},
        "tax_amount":        {"type": "number", "nullable": True},
        "detected_language": {"type": "string", "nullable": True},
        "raw_text":          {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_name":  {"type": "string"},
                    "quantity":   {"type": "number", "nullable": True},
                    "unit_price": {"type": "number", "nullable": True},
                    "item_price": {"type": "number"},
                },
                "required": ["item_name", "item_price"],
            },
        },
    },
    "required": ["raw_text", "items"],
}


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GeminiEngine(OCREngine):
    name = "gemini"

    def __init__(self, model: str | None = None):
        self.model = model or getattr(settings, "OCR_VLM_MODEL", "") or _DEFAULT_MODEL

    def extract(self, file_path: str) -> OCRResult:
        api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to backend/.env to use the gemini engine. "
                "Free key at https://aistudio.google.com/app/apikey."
            )

        if not os.path.exists(file_path):
            raise RuntimeError("Uploaded file not found on disk.")

        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise RuntimeError(
                "google-genai package missing. Install with `pip install google-genai`."
            ) from e

        client = genai.Client(api_key=api_key)

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        mime = "image/png" if file_path.lower().endswith(".png") else "image/jpeg"

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime),
                    _PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                    temperature=0.1,
                ),
            )
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {e}") from e

        import json

        try:
            data = json.loads(response.text)
        except (json.JSONDecodeError, AttributeError) as e:
            raise RuntimeError(f"Gemini returned non-JSON: {e}") from e

        raw_text = (data.get("raw_text") or "").strip()
        if not raw_text:
            raise RuntimeError("Gemini returned empty raw_text.")

        items_in = data.get("items") or []
        items: list[StructuredItem] = []
        for it in items_in:
            name = str(it.get("item_name", "")).strip()
            if not name:
                continue
            # Be defensive: Gemini occasionally returns "12.3A" or other
            # non-numeric strings for amounts. Skip rather than crash the
            # whole upload, which would block a paying user.
            try:
                price = float(it.get("item_price") or 0.0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            try:
                qty = float(it["quantity"]) if it.get("quantity") is not None else None
            except (TypeError, ValueError):
                qty = None
            try:
                unit = float(it["unit_price"]) if it.get("unit_price") is not None else None
            except (TypeError, ValueError):
                unit = None
            items.append(StructuredItem(
                item_name=name, quantity=qty, unit_price=unit, item_price=price,
            ))

        structured = StructuredReceipt(
            store_name=(data.get("store_name") or None),
            receipt_date=_parse_date(data.get("receipt_date")),
            currency=(data.get("currency") or "").upper() or None,
            total_amount=data.get("total_amount"),
            tax_amount=data.get("tax_amount"),
            detected_language=data.get("detected_language"),
            items=items,
        )

        return OCRResult(
            raw_text=raw_text,
            structured=structured,
            confidence=0.95,  # VLM with structured output — treat as high-confidence
            engine=self.name,
        )
