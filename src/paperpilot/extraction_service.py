"""Application services for structured document extraction."""

from time import perf_counter

from sqlalchemy.orm import Session

from paperpilot.extraction_repository import (
    create_extraction_result,
    get_latest_extraction_result,
    mark_extraction_failed,
    mark_extraction_succeeded,
)
from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
)
from paperpilot.extractor import (
    ExtractionError,
    StructuredExtractor,
)
from paperpilot.models import (
    DocumentRecord,
    ExtractionResult,
    ExtractionStatus,
    utc_now,
)
from paperpilot.ocr_repository import (
    get_latest_successful_ocr_result,
)


class NoSuccessfulOcrResultError(Exception):
    """Raised when no successful OCR result is available."""


class ExtractionAlreadyProcessedError(Exception):
    """Raised when a successful extraction already exists."""


class ExtractionProcessingInProgressError(Exception):
    """Raised when extraction is already running."""


class ExtractionProcessingError(Exception):
    """Raised when structured extraction fails."""


def process_document_extraction(
    session: Session,
    *,
    document: DocumentRecord,
    extractor: StructuredExtractor,
    allow_reprocess: bool = False,
) -> ExtractionResult:
    """Extract and persist structured data from OCR text."""
    latest_extraction = get_latest_extraction_result(
        session,
        document.id,
    )

    if (
        latest_extraction is not None
        and latest_extraction.status
        is ExtractionStatus.PROCESSING
    ):
        raise ExtractionProcessingInProgressError(
            "Structured extraction is already in progress."
        )

    if (
        latest_extraction is not None
        and latest_extraction.status
        is ExtractionStatus.SUCCEEDED
        and not allow_reprocess
    ):
        raise ExtractionAlreadyProcessedError(
            "This document has already been extracted."
        )

    ocr_result = get_latest_successful_ocr_result(
        session,
        document.id,
    )

    if (
        ocr_result is None
        or not ocr_result.text
        or not ocr_result.text.strip()
    ):
        raise NoSuccessfulOcrResultError(
            "A successful OCR result is required before extraction."
        )

    result = create_extraction_result(
        session,
        document_id=document.id,
        ocr_result_id=ocr_result.id,
        extractor=extractor.name,
        schema_version="1.0",
    )

    session.commit()
    session.refresh(result)

    started_at = perf_counter()

    try:
        extracted = extractor.extract(ocr_result.text)
    except Exception as exc:
        processing_time_ms = _elapsed_milliseconds(started_at)

        error_message = (
            str(exc)
            if isinstance(exc, ExtractionError)
            else "Unexpected structured extraction failure."
        )

        mark_extraction_failed(
            session,
            result,
            error_message=error_message,
            processing_time_ms=processing_time_ms,
            completed_at=utc_now(),
        )

        session.commit()
        session.refresh(result)

        raise ExtractionProcessingError(
            error_message
        ) from exc

    processing_time_ms = _elapsed_milliseconds(started_at)

    mark_extraction_succeeded(
        session,
        result,
        extracted_data=_serialize_extraction(extracted),
        processing_time_ms=processing_time_ms,
        completed_at=utc_now(),
    )

    session.commit()
    session.refresh(result)

    return result


def _serialize_extraction(
    extraction: FinancialDocumentExtractionV1,
) -> dict[str, object]:
    """Convert validated extraction data into JSON-safe values."""
    return extraction.model_dump(
        mode="json",
    )


def _elapsed_milliseconds(started_at: float) -> int:
    """Return elapsed processing time in milliseconds."""
    elapsed_seconds = perf_counter() - started_at

    return max(
        0,
        round(elapsed_seconds * 1_000),
    )