"""Application services for registering PaperPilot documents."""

from pathlib import Path

from sqlalchemy.orm import Session

from paperpilot.document_repository import (
    DuplicateDocumentError,
    create_document_record,
)
from paperpilot.document_storage import (
    get_document_path,
    normalize_filename,
    store_document_content,
)
from paperpilot.models import DocumentRecord

class StoredDocumentMissingError(Exception):
    """Raised when document metadata exists but its file is missing."""

def register_document(
    session: Session,
    *,
    filename: str | None,
    content_type: str,
    content: bytes,
    fingerprint: str,
    storage_root: Path,
) -> DocumentRecord:
    """Store document contents and persist their metadata."""
    safe_filename = normalize_filename(filename)

    destination = get_document_path(
        fingerprint=fingerprint,
        content_type=content_type,
        storage_root=storage_root,
    )
    destination_existed = destination.exists()

    try:
        record = create_document_record(
            session,
            filename=safe_filename,
            content_type=content_type,
            size_bytes=len(content),
            sha256=fingerprint,
        )

        store_document_content(
            content=content,
            fingerprint=fingerprint,
            content_type=content_type,
            storage_root=storage_root,
        )

        session.commit()
        session.refresh(record)

        return record

    except DuplicateDocumentError:
        session.rollback()
        raise

    except Exception:
        session.rollback()

        if not destination_existed and destination.exists():
            destination.unlink()

        raise

def get_stored_document_path(
    record: DocumentRecord,
    *,
    storage_root: Path,
) -> Path:
    """Return the stored file path for a document record."""
    stored_path = get_document_path(
        fingerprint=record.sha256,
        content_type=record.content_type,
        storage_root=storage_root,
    )

    if not stored_path.is_file():
        raise StoredDocumentMissingError(
            f"Stored file is missing for document {record.id}."
        )

    return stored_path