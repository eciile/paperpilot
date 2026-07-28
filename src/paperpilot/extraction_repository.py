"""Database operations for structured extraction results."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from paperpilot.models import (
    ExtractionResult,
    ExtractionStatus,
)


def create_extraction_result(
    session: Session,
    *,
    document_id: int,
    ocr_result_id: int,
    extractor: str,
    schema_version: str,
) -> ExtractionResult:
    """Create a processing extraction attempt."""
    result = ExtractionResult(
        document_id=document_id,
        ocr_result_id=ocr_result_id,
        extractor=extractor,
        schema_version=schema_version,
        status=ExtractionStatus.PROCESSING,
    )

    session.add(result)
    session.flush()

    return result


def get_latest_extraction_result(
    session: Session,
    document_id: int,
) -> ExtractionResult | None:
    """Return the newest extraction attempt for a document."""
    statement = (
        select(ExtractionResult)
        .where(
            ExtractionResult.document_id == document_id
        )
        .order_by(
            ExtractionResult.created_at.desc(),
            ExtractionResult.id.desc(),
        )
        .limit(1)
    )

    return session.scalar(statement)


def mark_extraction_succeeded(
    session: Session,
    result: ExtractionResult,
    *,
    extracted_data: dict[str, object],
    processing_time_ms: int,
    completed_at: datetime,
) -> ExtractionResult:
    """Store successful structured extraction output."""
    result.status = ExtractionStatus.SUCCEEDED
    result.extracted_data = extracted_data
    result.processing_time_ms = processing_time_ms
    result.error_message = None
    result.completed_at = completed_at

    session.flush()

    return result


def mark_extraction_failed(
    session: Session,
    result: ExtractionResult,
    *,
    error_message: str,
    processing_time_ms: int,
    completed_at: datetime,
) -> ExtractionResult:
    """Store extraction failure information."""
    result.status = ExtractionStatus.FAILED
    result.extracted_data = None
    result.processing_time_ms = processing_time_ms
    result.error_message = error_message
    result.completed_at = completed_at

    session.flush()

    return result