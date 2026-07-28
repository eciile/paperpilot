"""Tests for structured extraction database models."""

from sqlalchemy.orm import Session

from paperpilot.models import (
    DocumentRecord,
    ExtractionResult,
    ExtractionStatus,
    OcrResult,
    OcrStatus,
    utc_now,
)


def create_successful_ocr_result(
    session: Session,
) -> OcrResult:
    """Create the document and OCR result required by tests."""
    document = DocumentRecord(
        filename="invoice.png",
        content_type="image/png",
        size_bytes=1_024,
        sha256="b" * 64,
    )

    session.add(document)
    session.flush()

    ocr_result = OcrResult(
        document_id=document.id,
        status=OcrStatus.SUCCEEDED,
        engine="fake-ocr",
        text="Invoice INV-42 Total 42.00 EUR",
        average_confidence=0.94,
        processing_time_ms=500,
        completed_at=utc_now(),
    )

    session.add(ocr_result)
    session.flush()

    return ocr_result


def test_extraction_result_defaults_to_processing(
    database_session: Session,
) -> None:
    """A new extraction attempt should begin as processing."""
    ocr_result = create_successful_ocr_result(
        database_session
    )

    result = ExtractionResult(
        document_id=ocr_result.document_id,
        ocr_result_id=ocr_result.id,
        extractor="fake-extractor",
        schema_version="1.0",
    )

    database_session.add(result)
    database_session.flush()

    assert result.id > 0
    assert result.status is ExtractionStatus.PROCESSING
    assert result.extracted_data is None
    assert result.error_message is None
    assert result.completed_at is None


def test_successful_extraction_data_is_persisted(
    database_session: Session,
) -> None:
    """Validated structured data should persist as JSON."""
    ocr_result = create_successful_ocr_result(
        database_session
    )

    result = ExtractionResult(
        document_id=ocr_result.document_id,
        ocr_result_id=ocr_result.id,
        status=ExtractionStatus.SUCCEEDED,
        extractor="fake-extractor",
        schema_version="1.0",
        extracted_data={
            "schema_version": "1.0",
            "document_type": "invoice",
            "supplier_name": "Example Telecom",
            "currency": "EUR",
            "total": "42.00",
        },
        processing_time_ms=350,
        completed_at=utc_now(),
    )

    database_session.add(result)
    database_session.commit()

    stored_result = database_session.get(
        ExtractionResult,
        result.id,
    )

    assert stored_result is not None
    assert stored_result.status is ExtractionStatus.SUCCEEDED
    assert stored_result.ocr_result_id == ocr_result.id
    assert stored_result.extracted_data is not None
    assert stored_result.extracted_data["total"] == "42.00"
    assert stored_result.error_message is None