"""
Mindee receipt API engine.

Stub — Mindee is a purpose-built receipt extraction service. Their accuracy on
receipts specifically is higher than general-purpose VLMs, at higher cost
(~$0.05–$0.10/receipt). Worth the price for paid commercial tiers.

To enable:
  1. `pip install mindee` (their official Python SDK)
  2. Sign up at https://platform.mindee.com — they give 250 free pages/month
  3. Set MINDEE_API_KEY in backend/.env
  4. Implement extract() using mindee.Client().enqueue_and_parse(ReceiptV5, …)
  5. Set OCR_ENGINE=mindee

Their schema already matches our StructuredReceipt fairly closely, so
adaptation is mostly field renaming.
"""
from __future__ import annotations

from app.services.ocr_engines.base import OCREngine, OCRResult


class MindeeEngine(OCREngine):
    name = "mindee"

    def extract(self, file_path: str, context=None) -> OCRResult:
        raise NotImplementedError(
            "MindeeEngine is a stub. Install `mindee`, set MINDEE_API_KEY, "
            "and implement extract() using ReceiptV5 parser."
        )
