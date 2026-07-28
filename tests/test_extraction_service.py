"""Tests for the structured extraction service."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session
import pytest

from paperpilot.extraction_repository import (
    get_latest_extraction_result,
)
from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
    FinancialDocumentType,
)
from paperpilot.extraction_service import (
    ExtractionAlreadyProcessedError,
    ExtractionProcessingError,
    ExtractionProcessingInProgressError,
    NoSuccessfulOcrResultError,
    process_document_extraction,
)
from paperpilot.extractor import ExtractionError
from paperpilot.models import (
    DocumentRecord,
    ExtractionResult,
    ExtractionStatus,
    OcrResult,
    OcrStatus,
    utc_now,
)


class SuccessfulExtractor:
    """Deterministic extractor used in service tests."""

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


class FailingExtractor:
    """Extractor that always fails."""

    @property
    def name(self) -> str:
        """Return the fake extractor name."""
        return "failing-extractor"

    def extract(
        self,
        ocr_text: str,
    ) -> FinancialDocumentExtractionV1:
        """Simulate an extraction failure."""
        raise ExtractionError(
            "Simulated extraction failure."
        )


def create_document(
    session: Session,
) -> DocumentRecord:
    """Create a document for extraction tests."""
    document = DocumentRecord(
        filename="invoice.png",
        content_type="image/png",
        size_bytes=1_024,
        sha256="d" * 64,
    )

    session.add(document)
    session.flush()

    return document


def add_successful_ocr(
    session: Session,
    document: DocumentRecord,
) -> OcrResult:
    """Attach a successful OCR result to a document."""
    ocr_result = OcrResult(
        document_id=document.id,
        status=OcrStatus.SUCCEEDED,
        engine="fake-ocr",
        text=(
            "Invoice INV-42 from Example Telecom. "
            "Total: 42.00 EUR."
        ),
        average_confidence=0.94,
        processing_time_ms=500,
        completed_at=utc_now(),
    )

    session.add(ocr_result)
    session.flush()

    return ocr_result


def test_process_extraction_persists_success(
    database_session: Session,
) -> None:
    """Successful extraction should persist structured data."""
    document = create_document(database_session)
    ocr_result = add_successful_ocr(
        database_session,
        document,
    )

    result = process_document_extraction(
        database_session,
        document=document,
        extractor=SuccessfulExtractor(),
    )

    assert result.status is ExtractionStatus.SUCCEEDED
    assert result.ocr_result_id == ocr_result.id
    assert result.extractor == "fake-extractor"
    assert result.schema_version == "1.0"
    assert result.extracted_data is not None
    assert (
        result.extracted_data["supplier_name"]
        == "Example Telecom"
    )
    assert result.extracted_data["total"] == "42.00"
    assert result.processing_time_ms is not None
    assert result.processing_time_ms >= 0
    assert result.error_message is None
    assert result.completed_at is not None


def test_extraction_requires_successful_ocr(
    database_session: Session,
) -> None:
    """Extraction should require successful OCR text."""
    document = create_document(database_session)

    with pytest.raises(
        NoSuccessfulOcrResultError,
        match="successful OCR result is required",
    ):
        process_document_extraction(
            database_session,
            document=document,
            extractor=SuccessfulExtractor(),
        )

    stored_count = database_session.scalar(
        select(func.count()).select_from(
            ExtractionResult
        )
    )

    assert stored_count == 0


def test_extraction_failure_is_persisted(
    database_session: Session,
) -> None:
    """Extractor failures should remain visible in the database."""
    document = create_document(database_session)
    add_successful_ocr(
        database_session,
        document,
    )

    with pytest.raises(
        ExtractionProcessingError,
        match="Simulated extraction failure",
    ):
        process_document_extraction(
            database_session,
            document=document,
            extractor=FailingExtractor(),
        )

    stored_result = get_latest_extraction_result(
        database_session,
        document.id,
    )

    assert stored_result is not None
    assert stored_result.status is ExtractionStatus.FAILED
    assert stored_result.extracted_data is None
    assert (
        stored_result.error_message
        == "Simulated extraction failure."
    )
    assert stored_result.processing_time_ms is not None
    assert stored_result.completed_at is not None

def test_successful_extraction_prevents_reprocessing(
    database_session: Session,
) -> None:
    """A successful extraction should block another normal attempt."""
    document = create_document(database_session)
    add_successful_ocr(
        database_session,
        document,
    )

    process_document_extraction(
        database_session,
        document=document,
        extractor=SuccessfulExtractor(),
    )

    with pytest.raises(
        ExtractionAlreadyProcessedError,
        match="already been extracted",
    ):
        process_document_extraction(
            database_session,
            document=document,
            extractor=SuccessfulExtractor(),
        )

    stored_count = database_session.scalar(
        select(func.count()).select_from(
            ExtractionResult
        )
    )

    assert stored_count == 1


def test_explicit_reprocessing_creates_new_attempt(
    database_session: Session,
) -> None:
    """Explicit reprocessing should preserve both attempts."""
    document = create_document(database_session)
    add_successful_ocr(
        database_session,
        document,
    )

    first_result = process_document_extraction(
        database_session,
        document=document,
        extractor=SuccessfulExtractor(),
    )

    second_result = process_document_extraction(
        database_session,
        document=document,
        extractor=SuccessfulExtractor(),
        allow_reprocess=True,
    )

    assert first_result.id != second_result.id

    stored_count = database_session.scalar(
        select(func.count()).select_from(
            ExtractionResult
        )
    )

    assert stored_count == 2


def test_processing_attempt_blocks_parallel_extraction(
    database_session: Session,
) -> None:
    """An active extraction should block another attempt."""
    document = create_document(database_session)
    ocr_result = add_successful_ocr(
        database_session,
        document,
    )

    active_result = ExtractionResult(
        document_id=document.id,
        ocr_result_id=ocr_result.id,
        extractor="active-extractor",
        schema_version="1.0",
        status=ExtractionStatus.PROCESSING,
    )

    database_session.add(active_result)
    database_session.commit()

    with pytest.raises(
        ExtractionProcessingInProgressError,
        match="already in progress",
    ):
        process_document_extraction(
            database_session,
            document=document,
            extractor=SuccessfulExtractor(),
            allow_reprocess=True,
        )

    stored_count = database_session.scalar(
        select(func.count()).select_from(
            ExtractionResult
        )
    )

    assert stored_count == 1