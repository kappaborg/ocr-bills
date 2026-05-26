"""OCR engine plug-ins. The factory in app.services.ocr picks one at runtime."""

from app.services.ocr_engines.base import OCREngine, OCRResult, StructuredItem, StructuredReceipt

__all__ = ["OCREngine", "OCRResult", "StructuredItem", "StructuredReceipt"]
