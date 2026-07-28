"""Tests for the Ollama structured extractor."""

import pytest

from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
    FinancialDocumentType,
)
from paperpilot.extractor import (
    ExtractionError,
    StructuredExtractor,
)
from paperpilot.ollama_extractor import (
    OllamaStructuredExtractor,
)


class FakeStructuredModel:
    """Test double for a LangChain structured model."""

    def __init__(
        self,
        response: object,
        *,
        error: Exception | None = None,
    ) -> None:
        """Configure the fake model response."""
        self.response = response
        self.error = error
        self.received_inputs: list[object] = []

    def invoke(
        self,
        input: object,
    ) -> object:
        """Return the configured response."""
        self.received_inputs.append(input)

        if self.error is not None:
            raise self.error

        return self.response


def test_ollama_extractor_returns_validated_data() -> None:
    """A structured model response should be validated."""
    model = FakeStructuredModel(
        {
            "document_type": "invoice",
            "supplier_name": "Example Telecom",
            "document_number": "INV-42",
            "currency": "eur",
            "total": "42.00",
        }
    )

    extractor = OllamaStructuredExtractor(
        model_name="test-model",
        structured_model=model,
    )

    result = extractor.extract(
        "Invoice INV-42 from Example Telecom. "
        "Total: 42.00 EUR."
    )

    assert isinstance(extractor, StructuredExtractor)
    assert extractor.name == "ollama:test-model"

    assert isinstance(
        result,
        FinancialDocumentExtractionV1,
    )
    assert (
        result.document_type
        is FinancialDocumentType.INVOICE
    )
    assert result.supplier_name == "Example Telecom"
    assert result.document_number == "INV-42"
    assert result.currency == "EUR"
    assert str(result.total) == "42.00"

    assert len(model.received_inputs) == 1


def test_ollama_extractor_accepts_pydantic_result() -> None:
    """An already validated Pydantic result should be returned."""
    expected_result = FinancialDocumentExtractionV1(
        document_type=FinancialDocumentType.RECEIPT,
        supplier_name="Example Shop",
        currency="EUR",
        total="18.50",
    )

    model = FakeStructuredModel(expected_result)

    extractor = OllamaStructuredExtractor(
        structured_model=model,
    )

    result = extractor.extract(
        "Example Shop receipt. Total 18.50 EUR."
    )

    assert result is expected_result


def test_ollama_extractor_rejects_empty_text() -> None:
    """Blank OCR text should fail before invoking the model."""
    model = FakeStructuredModel({})

    extractor = OllamaStructuredExtractor(
        structured_model=model,
    )

    with pytest.raises(
        ExtractionError,
        match="OCR text is empty",
    ):
        extractor.extract("   ")

    assert model.received_inputs == []


def test_ollama_extractor_wraps_model_failure() -> None:
    """Model communication errors should become ExtractionError."""
    model = FakeStructuredModel(
        {},
        error=RuntimeError("Ollama unavailable"),
    )

    extractor = OllamaStructuredExtractor(
        structured_model=model,
    )

    with pytest.raises(
        ExtractionError,
        match="could not extract",
    ):
        extractor.extract(
            "Invoice INV-42. Total 42.00 EUR."
        )


def test_ollama_extractor_rejects_invalid_output() -> None:
    """Invalid structured output should be rejected."""
    model = FakeStructuredModel(
        {
            "document_type": "invoice",
            "currency": "EURO",
        }
    )

    extractor = OllamaStructuredExtractor(
        structured_model=model,
    )

    with pytest.raises(
        ExtractionError,
        match="invalid structured extraction data",
    ):
        extractor.extract(
            "Invoice with an invalid model response."
        )