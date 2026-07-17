"""Database models for PaperPilot."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Base class for PaperPilot database models."""

class DocumentRecord(Base):
    """metadata describing an accepted document"""
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    sha256: Mapped[str]=mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    created_at: Mapped[datetime]= mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
