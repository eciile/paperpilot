"""Database operations for PaperPilot documents."""

from sqlalchemy.orm import Session

from paperpilot.models import DocumentRecord


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
    session.commit()
    session.refresh(record)

    return record