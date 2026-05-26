"""
PaddleOCR engine.

Stub — PaddleOCR is the strongest open-source OCR for multi-script receipts.
Zero per-receipt cost, runs locally on CPU/GPU. The blocker on this codebase
is Python 3.14 — PaddlePaddle has no 3.14 wheel as of 2026-05.

To enable when wheels land (or via a sidecar 3.12 venv + subprocess):
  1. Create a separate venv with Python 3.12:
       /opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv-ocr
       .venv-ocr/bin/pip install paddlepaddle paddleocr
  2. Expose a tiny CLI in that venv that prints JSON to stdout
  3. Implement extract() to subprocess.run(...) into it and parse JSON
  4. Set OCR_ENGINE=paddle

When Python 3.14 wheels eventually land, replace the subprocess hop with a
direct `from paddleocr import PaddleOCR` import.
"""
from __future__ import annotations

from app.services.ocr_engines.base import OCREngine, OCRResult


class PaddleEngine(OCREngine):
    name = "paddle"

    def extract(self, file_path: str) -> OCRResult:
        raise NotImplementedError(
            "PaddleEngine is a stub. Set up the sidecar 3.12 venv or wait for "
            "Py 3.14 wheels, then implement extract()."
        )
