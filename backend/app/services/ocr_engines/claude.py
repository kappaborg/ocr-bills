"""
Claude vision engine (Anthropic).

Stub — drop-in spot for an Anthropic Messages API implementation. The pattern
mirrors `gemini.py`: load image bytes, call `client.messages.create(...)` with
a `tool_use` that returns structured fields, parse into a StructuredReceipt.

To enable:
  1. `pip install anthropic`
  2. Set ANTHROPIC_API_KEY in backend/.env
  3. Implement extract() — adapt the prompt + schema from gemini.py
  4. Set OCR_ENGINE=claude

Cost: ~$0.005/receipt on claude-haiku-4-5, ~$0.01 on claude-sonnet-4.
"""
from __future__ import annotations

from app.services.ocr_engines.base import OCREngine, OCRResult


class ClaudeEngine(OCREngine):
    name = "claude"

    def extract(self, file_path: str, context=None) -> OCRResult:
        raise NotImplementedError(
            "ClaudeEngine is a stub. Install `anthropic`, set ANTHROPIC_API_KEY, "
            "and implement extract() — see gemini.py for the structured-output pattern."
        )
