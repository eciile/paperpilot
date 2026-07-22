"""Application services for processing documents with OCR."""

from pathlib import Path
from time import perf_counter

from sqlalchemy.orm import Session

from paperpilot.document_service import get_stored_document_path
from paperpilot.models import (
    DocumentRecord,
    OcrResult,
    OcrStatus,
    utc_now,
)
from paperpilot.ocr_engine import OcrEngine, OcrEngineError
from paperpilot.ocr_repository import (
    create_ocr_result,
    get_latest_ocr_result,
    mark_ocr_result_failed,
    mark_ocr_result_succeeded,
)


class OcrAlreadyProcessedError(Exception):
    """Raised when a completed OCR result already exists."""


class OcrProcessingInProgressError(Exception):
    """Raised when the document already has an active OCR attempt."""


class OcrProcessingError(Exception):
    """Raised when an OCR engine fails to process a document."""


def process_document_ocr(
    session: Session,
    *,
    document: DocumentRecord,
    storage_root: Path,
    engine: OcrEngine,
    allow_reprocess: bool = False,
) -> OcrResult:
    """Process a stored document and persist the OCR result."""
    latest_result = get_latest_ocr_result(
        session,
        document.id,
    )

    if (
        latest_result is not None
        and latest_result.status
        in {
            OcrStatus.PENDING,
            OcrStatus.PROCESSING,
        }
    ):
        raise OcrProcessingInProgressError(
            "OCR processing is already in progress for this document."
        )

    if (
        latest_result is not None
        and latest_result.status is OcrStatus.SUCCEEDED
        and not allow_reprocess
    ):
        raise OcrAlreadyProcessedError(
            "This document has already been processed with OCR."
        )

    document_path = get_stored_document_path(
        document,
        storage_root=storage_root,
    )

    result = create_ocr_result(
        session,
        document_id=document.id,
        engine=engine.name,
        status=OcrStatus.PROCESSING,
    )

    session.commit()
    session.refresh(result)

    started_at = perf_counter()

    try:
        output = engine.extract(
            document_path,
            content_type=document.content_type,
        )
    except Exception as exc:
        processing_time_ms = _elapsed_milliseconds(started_at)

        if isinstance(exc, OcrEngineError):
            error_message = str(exc)
        else:
            error_message = "Unexpected OCR processing failure."

        mark_ocr_result_failed(
            session,
            result,
            error_message=error_message,
            processing_time_ms=processing_time_ms,
            completed_at=utc_now(),
        )

        session.commit()
        session.refresh(result)

        raise OcrProcessingError(error_message) from exc

    processing_time_ms = _elapsed_milliseconds(started_at)

    mark_ocr_result_succeeded(
        session,
        result,
        text=output.text,
        average_confidence=output.average_confidence,
        processing_time_ms=processing_time_ms,
        completed_at=utc_now(),
    )

    session.commit()
    session.refresh(result)

    return result


def _elapsed_milliseconds(started_at: float) -> int:
    """Return elapsed processing time as non-negative milliseconds."""
    elapsed_seconds = perf_counter() - started_at

    return max(
        0,
        round(elapsed_seconds * 1_000),
    )