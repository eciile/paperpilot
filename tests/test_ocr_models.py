"""Tests for OCR database models."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from paperpilot.models import (
    DocumentRecord,
    OcrResult,
    OcrStatus,
)


def create_test_document(
    session: Session,
) -> DocumentRecord:
    """Create a document record required by OCR model tests."""
    document = DocumentRecord(
        filename="invoice.pdf",
        content_type="application/pdf",
        size_bytes=1_024,
        sha256="a" * 64,
    )

    session.add(document)
    session.flush()

    return document


def test_ocr_result_defaults_to_pending(
    database_session: Session,
) -> None:
    """A new OCR result should begin in the pending state."""
    document = create_test_document(database_session)

    result = OcrResult(
        document_id=document.id,
        engine="test-engine",
    )

    database_session.add(result)
    database_session.flush()

    assert result.id > 0
    assert result.status is OcrStatus.PENDING
    assert result.text is None
    assert result.average_confidence is None
    assert result.error_message is None
    assert result.completed_at is None


def test_successful_ocr_result_persists_processing_metadata(
    database_session: Session,
) -> None:
    """A completed OCR result should persist its output metadata."""
    document = create_test_document(database_session)
    completed_at = datetime.now(timezone.utc)

    result = OcrResult(
        document_id=document.id,
        status=OcrStatus.SUCCEEDED,
        engine="test-engine",
        text="Supplier: Example Telecom\nTotal: 42.00 EUR",
        average_confidence=0.93,
        processing_time_ms=1_250,
        completed_at=completed_at,
    )

    database_session.add(result)
    database_session.flush()

    result_id = result.id

    database_session.commit()
    database_session.expire_all()

    stored_result = database_session.get(
        OcrResult,
        result_id,
    )

    assert stored_result is not None
    assert stored_result.document_id == document.id
    assert stored_result.status is OcrStatus.SUCCEEDED
    assert stored_result.engine == "test-engine"
    assert stored_result.text == (
        "Supplier: Example Telecom\n"
        "Total: 42.00 EUR"
    )
    assert stored_result.average_confidence == 0.93
    assert stored_result.processing_time_ms == 1_250
    assert stored_result.error_message is None
    assert stored_result.completed_at is not None