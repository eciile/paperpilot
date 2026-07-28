"""Tests for structured extraction schemas."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
    FinancialDocumentType,
)


def test_financial_document_schema_parses_values() -> None:
    """Valid extracted values should be normalized."""
    extraction = FinancialDocumentExtractionV1.model_validate(
        {
            "document_type": "invoice",
            "supplier_name": " Example Telecom ",
            "document_number": " INV-42 ",
            "issue_date": "2026-06-01",
            "due_date": "2026-06-30",
            "currency": "eur",
            "subtotal": "35.00",
            "tax": "7.00",
            "total": "42.00",
        }
    )

    assert extraction.schema_version == "1.0"
    assert (
        extraction.document_type
        is FinancialDocumentType.INVOICE
    )
    assert extraction.supplier_name == "Example Telecom"
    assert extraction.document_number == "INV-42"
    assert extraction.issue_date == date(2026, 6, 1)
    assert extraction.due_date == date(2026, 6, 30)
    assert extraction.currency == "EUR"
    assert extraction.subtotal == Decimal("35.00")
    assert extraction.tax == Decimal("7.00")
    assert extraction.total == Decimal("42.00")


def test_blank_optional_text_becomes_none() -> None:
    """Blank extracted strings should become null."""
    extraction = FinancialDocumentExtractionV1(
        document_type=FinancialDocumentType.UNKNOWN,
        supplier_name="   ",
        document_number="",
        currency=" ",
    )

    assert extraction.supplier_name is None
    assert extraction.document_number is None
    assert extraction.currency is None


def test_unknown_document_can_have_missing_fields() -> None:
    """Unknown documents should not require invented values."""
    extraction = FinancialDocumentExtractionV1(
        document_type=FinancialDocumentType.UNKNOWN,
    )

    assert extraction.total is None
    assert extraction.issue_date is None
    assert extraction.supplier_name is None


def test_invalid_currency_is_rejected() -> None:
    """Currency must use a three-letter code."""
    with pytest.raises(
        ValidationError,
        match="three-letter code",
    ):
        FinancialDocumentExtractionV1(
            document_type=FinancialDocumentType.RECEIPT,
            currency="EURO",
        )


def test_unexpected_fields_are_rejected() -> None:
    """Fields outside version 1 should not be accepted."""
    with pytest.raises(ValidationError):
        FinancialDocumentExtractionV1.model_validate(
            {
                "document_type": "invoice",
                "total": "42.00",
                "line_items": [],
            }
        )


def test_unsupported_schema_version_is_rejected() -> None:
    """Version 1 should reject another schema version."""
    with pytest.raises(ValidationError):
        FinancialDocumentExtractionV1.model_validate(
            {
                "schema_version": "2.0",
                "document_type": "invoice",
            }
        )