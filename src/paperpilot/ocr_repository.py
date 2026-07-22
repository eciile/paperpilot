"""Database operations for PaperPilot OCR results."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from paperpilot.models import OcrResult, OcrStatus


def create_ocr_result(
    session: Session,
    *,
    document_id: int,
    engine: str,
    status: OcrStatus = OcrStatus.PROCESSING,
) -> OcrResult:
    """Create an OCR processing result in the current transaction."""
    result = OcrResult(
        document_id=document_id,
        engine=engine,
        status=status,
    )

    session.add(result)
    session.flush()

    return result


def get_latest_ocr_result(
    session: Session,
    document_id: int,
) -> OcrResult | None:
    """Return the newest OCR result for a document."""
    statement = (
        select(OcrResult)
        .where(OcrResult.document_id == document_id)
        .order_by(
            OcrResult.created_at.desc(),
            OcrResult.id.desc(),
        )
        .limit(1)
    )

    return session.scalar(statement)


def mark_ocr_result_succeeded(
    session: Session,
    result: OcrResult,
    *,
    text: str,
    average_confidence: float | None,
    processing_time_ms: int,
    completed_at: datetime,
) -> OcrResult:
    """Update an OCR result with successful processing output."""
    result.status = OcrStatus.SUCCEEDED
    result.text = text
    result.average_confidence = average_confidence
    result.processing_time_ms = processing_time_ms
    result.error_message = None
    result.completed_at = completed_at

    session.flush()

    return result


def mark_ocr_result_failed(
    session: Session,
    result: OcrResult,
    *,
    error_message: str,
    processing_time_ms: int,
    completed_at: datetime,
) -> OcrResult:
    """Update an OCR result with failure information."""
    result.status = OcrStatus.FAILED
    result.text = None
    result.average_confidence = None
    result.processing_time_ms = processing_time_ms
    result.error_message = error_message
    result.completed_at = completed_at

    session.flush()

    return result