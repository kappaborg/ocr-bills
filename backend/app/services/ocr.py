"""
OCR dispatcher.

The actual engines live in `app/services/ocr_engines/`. This module:
  - resolves the configured engine via `settings.OCR_ENGINE`
  - preserves the legacy `extract_text_from_image(path) -> str` contract used
    everywhere in the codebase
  - exposes a richer `run_ocr(path) -> OCRResult` for callers that want the
    structured fields (used by `receipt_processing.py` to skip the regex
    parser when a VLM engine already extracted everything).

Add a new engine: drop a module in ocr_engines/, register it in
_ENGINE_REGISTRY below, and flip OCR_ENGINE in .env.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.ocr_engines.base import OCREngine, OCRResult
from app.services.ocr_engines.claude import ClaudeEngine
from app.services.ocr_engines.gemini import GeminiEngine
from app.services.ocr_engines.mindee import MindeeEngine
from app.services.ocr_engines.paddle import PaddleEngine
from app.services.ocr_engines.tesseract import TesseractEngine


_ENGINE_REGISTRY: dict[str, type[OCREngine]] = {
    "tesseract": TesseractEngine,
    "gemini":    GeminiEngine,
    "claude":    ClaudeEngine,
    "mindee":    MindeeEngine,
    "paddle":    PaddleEngine,
}


@lru_cache(maxsize=1)
def _get_engine() -> OCREngine:
    name = (getattr(settings, "OCR_ENGINE", "") or "tesseract").lower().strip()
    cls = _ENGINE_REGISTRY.get(name)
    if cls is None:
        raise RuntimeError(
            f"Unknown OCR_ENGINE='{name}'. Valid: {sorted(_ENGINE_REGISTRY)}"
        )
    return cls()


def run_ocr(file_path: str) -> OCRResult:
    """Run the configured OCR engine. Returns raw text plus optional structured fields."""
    return _get_engine().extract(file_path)


def extract_text_from_image(file_path: str) -> str:
    """Legacy contract — returns raw OCR text only. New code should call `run_ocr`."""
    return run_ocr(file_path).raw_text
