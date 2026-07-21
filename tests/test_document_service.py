"""Tests for document registration services."""

from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from paperpilot.document_service import (
    StoredDocumentMissingError,
    get_stored_document_path,
    register_document,
)
from paperpilot.document_storage import (
    DocumentStorageError,
    get_document_path,
)
from paperpilot.models import DocumentRecord


def test_register_document_stores_file_and_metadata(
    database_session: Session,
    storage_root: Path,
) -> None:
    """Registration should persist metadata and original contents."""
    content = b"%PDF-example invoice"
    fingerprint = sha256(content).hexdigest()

    record = register_document(
        database_session,
        filename="../../invoice.pdf",
        content_type="application/pdf",
        content=content,
        fingerprint=fingerprint,
        storage_root=storage_root,
    )

    assert record.id > 0
    assert record.filename == "invoice.pdf"
    assert record.content_type == "application/pdf"
    assert record.size_bytes == len(content)
    assert record.sha256 == fingerprint

    stored_path = get_document_path(
        fingerprint=fingerprint,
        content_type="application/pdf",
        storage_root=storage_root,
    )

    assert stored_path.exists()
    assert stored_path.read_bytes() == content


def test_register_document_rolls_back_when_storage_fails(
    database_session: Session,
    storage_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A storage failure should not leave database metadata behind."""
    content = b"%PDF-storage failure"
    fingerprint = sha256(content).hexdigest()

    def fail_storage(**_: object) -> Path:
        raise DocumentStorageError("Simulated storage failure.")

    monkeypatch.setattr(
        "paperpilot.document_service.store_document_content",
        fail_storage,
    )

    with pytest.raises(
        DocumentStorageError,
        match="Simulated storage failure",
    ):
        register_document(
            database_session,
            filename="invoice.pdf",
            content_type="application/pdf",
            content=content,
            fingerprint=fingerprint,
            storage_root=storage_root,
        )

    stored_count = database_session.scalar(
        select(func.count()).select_from(DocumentRecord)
    )

    assert stored_count == 0

    expected_path = get_document_path(
        fingerprint=fingerprint,
        content_type="application/pdf",
        storage_root=storage_root,
    )

    assert not expected_path.exists()

def test_get_stored_document_path_rejects_missing_file(
    database_session: Session,
    storage_root: Path,
) -> None:
    """A record without its stored file should raise an error."""
    content = b"%PDF-document that will disappear"
    fingerprint = sha256(content).hexdigest()

    record = register_document(
        database_session,
        filename="missing.pdf",
        content_type="application/pdf",
        content=content,
        fingerprint=fingerprint,
        storage_root=storage_root,
    )

    stored_path = get_document_path(
        fingerprint=fingerprint,
        content_type="application/pdf",
        storage_root=storage_root,
    )

    stored_path.unlink()

    with pytest.raises(
        StoredDocumentMissingError,
        match="Stored file is missing",
    ):
        get_stored_document_path(
            record,
            storage_root=storage_root,
        )