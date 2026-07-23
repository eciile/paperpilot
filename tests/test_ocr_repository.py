"""Tests for OCR database operations."""

from sqlalchemy.orm import Session

from paperpilot.models import (
    DocumentRecord,
    OcrStatus,
    utc_now,
)
from paperpilot.ocr_repository import (
    create_ocr_result,
    get_latest_ocr_result,
    mark_ocr_result_failed,
    mark_ocr_result_succeeded,
)


def create_document(
    session: Session,
) -> DocumentRecord:
    """Create a document required by OCR repository tests."""
    document = DocumentRecord(
        filename="invoice.pdf",
        content_type="application/pdf",
        size_bytes=1_024,
        sha256="a" * 64,
    )

    session.add(document)
    session.flush()

    return document


def test_get_latest_ocr_result_returns_none_when_missing(
    database_session: Session,
) -> None:
    """A document without OCR attempts should return no result."""
    document = create_document(database_session)

    result = get_latest_ocr_result(
        database_session,
        document.id,
    )

    assert result is None


def test_get_latest_ocr_result_returns_newest_attempt(
    database_session: Session,
) -> None:
    """The latest OCR attempt should be returned."""
    document = create_document(database_session)

    first_result = create_ocr_result(
        database_session,
        document_id=document.id,
        engine="first-engine",
    )
    second_result = create_ocr_result(
        database_session,
        document_id=document.id,
        engine="second-engine",
    )

    latest_result = get_latest_ocr_result(
        database_session,
        document.id,
    )

    assert latest_result is not None
    assert latest_result.id == second_result.id
    assert latest_result.id != first_result.id
    assert latest_result.engine == "second-engine"


def test_mark_ocr_result_succeeded_updates_output(
    database_session: Session,
) -> None:
    """A successful attempt should store its OCR output."""
    document = create_document(database_session)

    result = create_ocr_result(
        database_session,
        document_id=document.id,
        engine="test-engine",
    )

    completed_at = utc_now()

    mark_ocr_result_succeeded(
        database_session,
        result,
        text="Invoice number: INV-42",
        average_confidence=0.94,
        processing_time_ms=850,
        completed_at=completed_at,
    )

    assert result.status is OcrStatus.SUCCEEDED
    assert result.text == "Invoice number: INV-42"
    assert result.average_confidence == 0.94
    assert result.processing_time_ms == 850
    assert result.error_message is None
    assert result.completed_at == completed_at


def test_mark_ocr_result_failed_stores_error(
    database_session: Session,
) -> None:
    """A failed attempt should store failure information."""
    document = create_document(database_session)

    result = create_ocr_result(
        database_session,
        document_id=document.id,
        engine="test-engine",
    )

    completed_at = utc_now()

    mark_ocr_result_failed(
        database_session,
        result,
        error_message="OCR model failed.",
        processing_time_ms=275,
        completed_at=completed_at,
    )

    assert result.status is OcrStatus.FAILED
    assert result.text is None
    assert result.average_confidence is None
    assert result.processing_time_ms == 275
    assert result.error_message == "OCR model failed."
    assert result.completed_at == completed_at