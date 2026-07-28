"""Tests for structured extraction database operations."""

from sqlalchemy.orm import Session

from paperpilot.extraction_repository import (
    create_extraction_result,
    get_latest_extraction_result,
    mark_extraction_failed,
    mark_extraction_succeeded,
)
from paperpilot.models import (
    DocumentRecord,
    ExtractionStatus,
    OcrResult,
    OcrStatus,
    utc_now,
)


def create_successful_ocr_result(
    session: Session,
) -> OcrResult:
    """Create a document and successful OCR result."""
    document = DocumentRecord(
        filename="invoice.png",
        content_type="image/png",
        size_bytes=1_024,
        sha256="c" * 64,
    )

    session.add(document)
    session.flush()

    ocr_result = OcrResult(
        document_id=document.id,
        status=OcrStatus.SUCCEEDED,
        engine="fake-ocr",
        text="Invoice INV-42. Total: 42.00 EUR.",
        average_confidence=0.94,
        processing_time_ms=500,
        completed_at=utc_now(),
    )

    session.add(ocr_result)
    session.flush()

    return ocr_result


def test_get_latest_extraction_returns_none_when_missing(
    database_session: Session,
) -> None:
    """A document without extraction attempts should return none."""
    ocr_result = create_successful_ocr_result(
        database_session
    )

    result = get_latest_extraction_result(
        database_session,
        ocr_result.document_id,
    )

    assert result is None


def test_get_latest_extraction_returns_newest_attempt(
    database_session: Session,
) -> None:
    """The newest extraction attempt should be returned."""
    ocr_result = create_successful_ocr_result(
        database_session
    )

    first_result = create_extraction_result(
        database_session,
        document_id=ocr_result.document_id,
        ocr_result_id=ocr_result.id,
        extractor="first-extractor",
        schema_version="1.0",
    )

    second_result = create_extraction_result(
        database_session,
        document_id=ocr_result.document_id,
        ocr_result_id=ocr_result.id,
        extractor="second-extractor",
        schema_version="1.0",
    )

    latest_result = get_latest_extraction_result(
        database_session,
        ocr_result.document_id,
    )

    assert latest_result is not None
    assert latest_result.id == second_result.id
    assert latest_result.id != first_result.id
    assert latest_result.extractor == "second-extractor"


def test_mark_extraction_succeeded_stores_data(
    database_session: Session,
) -> None:
    """A successful extraction should store structured data."""
    ocr_result = create_successful_ocr_result(
        database_session
    )

    result = create_extraction_result(
        database_session,
        document_id=ocr_result.document_id,
        ocr_result_id=ocr_result.id,
        extractor="fake-extractor",
        schema_version="1.0",
    )

    completed_at = utc_now()

    mark_extraction_succeeded(
        database_session,
        result,
        extracted_data={
            "schema_version": "1.0",
            "document_type": "invoice",
            "currency": "EUR",
            "total": "42.00",
        },
        processing_time_ms=300,
        completed_at=completed_at,
    )

    assert result.status is ExtractionStatus.SUCCEEDED
    assert result.extracted_data is not None
    assert result.extracted_data["total"] == "42.00"
    assert result.processing_time_ms == 300
    assert result.error_message is None
    assert result.completed_at == completed_at


def test_mark_extraction_failed_stores_error(
    database_session: Session,
) -> None:
    """A failed extraction should store its error."""
    ocr_result = create_successful_ocr_result(
        database_session
    )

    result = create_extraction_result(
        database_session,
        document_id=ocr_result.document_id,
        ocr_result_id=ocr_result.id,
        extractor="fake-extractor",
        schema_version="1.0",
    )

    completed_at = utc_now()

    mark_extraction_failed(
        database_session,
        result,
        error_message="Invalid model output.",
        processing_time_ms=150,
        completed_at=completed_at,
    )

    assert result.status is ExtractionStatus.FAILED
    assert result.extracted_data is None
    assert result.processing_time_ms == 150
    assert result.error_message == "Invalid model output."
    assert result.completed_at == completed_at