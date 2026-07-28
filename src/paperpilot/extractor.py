"""Common interface for structured document extractors."""

from typing import Protocol, runtime_checkable

from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
)


class ExtractionError(RuntimeError):
    """Raised when structured extraction cannot be completed."""


@runtime_checkable
class StructuredExtractor(Protocol):
    """Interface implemented by structured-data extractors."""

    @property
    def name(self) -> str:
        """Return the stable extractor name."""
        ...

    def extract(
        self,
        ocr_text: str,
    ) -> FinancialDocumentExtractionV1:
        """Extract validated financial data from OCR text."""
        ...