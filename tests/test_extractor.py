"""Tests for the structured extractor interface."""

from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
    FinancialDocumentType,
)
from paperpilot.extractor import StructuredExtractor


class FakeStructuredExtractor:
    """Deterministic extractor used for interface testing."""

    @property
    def name(self) -> str:
        """Return the fake extractor name."""
        return "fake-extractor"

    def extract(
        self,
        ocr_text: str,
    ) -> FinancialDocumentExtractionV1:
        """Return deterministic structured data."""
        assert "INV-42" in ocr_text

        return FinancialDocumentExtractionV1(
            document_type=FinancialDocumentType.INVOICE,
            supplier_name="Example Telecom",
            document_number="INV-42",
            currency="EUR",
            total="42.00",
        )


def test_fake_extractor_implements_protocol() -> None:
    """A compatible extractor should satisfy the protocol."""
    extractor = FakeStructuredExtractor()

    assert isinstance(
        extractor,
        StructuredExtractor,
    )
    assert extractor.name == "fake-extractor"


def test_fake_extractor_returns_validated_schema() -> None:
    """Extractor output should use the versioned schema."""
    extractor = FakeStructuredExtractor()

    result = extractor.extract(
        "Invoice INV-42 from Example Telecom. "
        "Total: 42.00 EUR."
    )

    assert isinstance(
        result,
        FinancialDocumentExtractionV1,
    )
    assert result.schema_version == "1.0"
    assert (
        result.document_type
        is FinancialDocumentType.INVOICE
    )
    assert result.supplier_name == "Example Telecom"
    assert result.document_number == "INV-42"
    assert result.currency == "EUR"
    assert str(result.total) == "42.00"