"""Tests for document database operations."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from paperpilot.document_repository import create_document_record
from paperpilot.models import Base, DocumentRecord


def test_create_document_record_persists_metadata() -> None:
    """Creating a record should persist its document metadata."""
    test_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        created_record = create_document_record(
            session,
            filename="electricity-bill.pdf",
            content_type="application/pdf",
            size_bytes=42_000,
            sha256="a" * 64,
        )

        created_id = created_record.id

    with Session(test_engine) as session:
        stored_record = session.scalar(
            select(DocumentRecord).where(
                DocumentRecord.id == created_id
            )
        )

        assert stored_record is not None
        assert stored_record.filename == "electricity-bill.pdf"
        assert stored_record.content_type == "application/pdf"
        assert stored_record.size_bytes == 42_000
        assert stored_record.sha256 == "a" * 64
        assert stored_record.created_at is not None