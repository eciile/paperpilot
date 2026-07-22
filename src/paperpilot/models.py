"""Database models for PaperPilot."""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def utc_now() -> datetime:
    """Return the current UTC time timezone aware."""
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):

    """Base class for PaperPilot database models."""

class OcrStatus(StrEnum):

    """Possible states of OCR processing attempts."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class DocumentRecord(Base):
    """metadata describing an accepted document"""
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

class OcrResult(Base):
    """Persisted result of one OCR processing attempt."""

    __tablename__ = "ocr_results"

    __table_args__ = (
        CheckConstraint(
            (
                "average_confidence IS NULL "
                "OR (average_confidence >= 0.0 "
                "AND average_confidence <= 1.0)"
            ),
            name="ck_ocr_results_average_confidence",
        ),
        CheckConstraint(
            (
                "processing_time_ms IS NULL "
                "OR processing_time_ms >= 0"
            ),
            name="ck_ocr_results_processing_time_ms",
        ),
        Index(
            "ix_ocr_results_document_created_at",
            "document_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
    )

    status: Mapped[OcrStatus] = mapped_column(
        SqlEnum(
            OcrStatus,
            name="ocr_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_type: [
                member.value
                for member in enum_type
            ],
        ),
        default=OcrStatus.PENDING,
        index=True,
    )

    engine: Mapped[str] = mapped_column(String(100))

    text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    average_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    processing_time_ms: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
