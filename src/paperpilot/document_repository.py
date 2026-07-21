"""Database operations for PaperPilot documents."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from paperpilot.models import DocumentRecord


class DuplicateDocumentError(Exception):
    """Raised when a document fingerprint already exists."""


def create_document_record(
    session: Session,
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    sha256: str,
) -> DocumentRecord:
    """Create and persist a document metadata record."""
    record = DocumentRecord(
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
    )

    session.add(record)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        if get_document_by_sha256(session, sha256) is not None:
            raise DuplicateDocumentError from exc

        raise

    session.refresh(record)

    return record


def get_document_by_id(
    session: Session,
    document_id: int,
) -> DocumentRecord | None:
    """Return a document by its primary key."""
    return session.get(DocumentRecord, document_id)


def get_document_by_sha256(
    session: Session,
    sha256: str,
) -> DocumentRecord | None:
    """Return a document with the given fingerprint."""
    statement = select(DocumentRecord).where(
        DocumentRecord.sha256 == sha256
    )

    return session.scalar(statement)


def list_document_records(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 20,
) -> list[DocumentRecord]:
    """Return a page of documents ordered from newest to oldest."""
    statement = (
        select(DocumentRecord)
        .order_by(
            DocumentRecord.created_at.desc(),
            DocumentRecord.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(session.scalars(statement))