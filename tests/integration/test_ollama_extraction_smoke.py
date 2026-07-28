"""Optional smoke test for a real local Ollama model."""

import os

import pytest

from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
)
from paperpilot.ollama_extractor import (
    OllamaStructuredExtractor,
)


@pytest.mark.skipif(
    os.getenv("PAPERPILOT_OLLAMA_SMOKE") != "1",
    reason=(
        "Set PAPERPILOT_OLLAMA_SMOKE=1 to run the real "
        "Ollama smoke test."
    ),
)
def test_real_ollama_extracts_invoice_data() -> None:
    """Run structured extraction using the configured Ollama model."""
    model_name = os.getenv(
        "PAPERPILOT_OLLAMA_MODEL",
        "qwen2.5:7b",
    )

    extractor = OllamaStructuredExtractor(
        model_name=model_name,
    )

    result = extractor.extract(
        "Invoice INV-42 from Example Telecom. "
        "Issue date: 2026-06-01. "
        "Subtotal: 35.00 EUR. "
        "Tax: 7.00 EUR. "
        "Total: 42.00 EUR."
    )

    assert isinstance(
        result,
        FinancialDocumentExtractionV1,
    )
    assert result.schema_version == "1.0"