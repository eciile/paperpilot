"""Validated schemas for structured document extraction."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    WithJsonSchema,
    field_validator,
)


class FinancialDocumentType(StrEnum):
    """Supported financial document categories."""

    INVOICE = "invoice"
    RECEIPT = "receipt"
    UTILITY_BILL = "utility_bill"
    UNKNOWN = "unknown"

MoneyAmount = Annotated[
    Decimal | None,
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number"},
                {"type": "null"},
            ]
        }
    ),
]

class FinancialDocumentExtractionV1(BaseModel):
    """Version 1 structured extraction for financial documents."""

    model_config = ConfigDict(
        extra="forbid",
    )

    schema_version: Literal["1.0"] = "1.0"

    document_type: FinancialDocumentType

    supplier_name: str | None = None
    document_number: str | None = None

    issue_date: date | None = None
    due_date: date | None = None

    currency: str | None = None

    subtotal: MoneyAmount = None
    tax: MoneyAmount = None
    total: MoneyAmount = None

    @field_validator(
        "supplier_name",
        "document_number",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """Strip text and convert blank values to null."""
        if not isinstance(value, str):
            return value

        normalized = value.strip()

        return normalized or None

    @field_validator(
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_currency(
        cls,
        value: object,
    ) -> object:
        """Normalize three-letter currency codes."""
        if not isinstance(value, str):
            return value

        normalized = value.strip().upper()

        if not normalized:
            return None

        if (
            len(normalized) != 3
            or not normalized.isalpha()
        ):
            raise ValueError(
                "Currency must be a three-letter code."
            )

        return normalized