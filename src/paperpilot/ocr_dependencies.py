"""FastAPI dependencies for PaperPilot OCR engines."""

from functools import lru_cache

from paperpilot.ocr_engine import OcrEngine
from paperpilot.paddle_ocr_engine import PaddleOcrEngine


@lru_cache(maxsize=1)
def get_ocr_engine() -> OcrEngine:
    """Return the shared OCR engine used by the application."""
    return PaddleOcrEngine()