"""FastAPI dependencies for structured document extraction."""

from functools import lru_cache

from paperpilot.extractor import StructuredExtractor
from paperpilot.ollama_extractor import (
    OllamaStructuredExtractor,
)


@lru_cache(maxsize=1)
def get_structured_extractor() -> StructuredExtractor:
    """Return the shared structured extractor."""
    return OllamaStructuredExtractor()