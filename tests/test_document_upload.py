"""Tests for document upload validation and persistence."""

from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from paperpilot.main import MAX_FILE_SIZE_BYTES
from paperpilot.models import DocumentRecord
from pathlib import Path
from paperpilot.document_storage import get_document_path

def test_inspect_png_document(
    client: TestClient,
    database_session: Session,
    storage_root: Path,
) -> None:
    """A supported PNG upload should be persisted and returned."""
    content = b"\x89PNG\r\n\x1a\n" + b"example image content"

    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "receipt.png",
                content,
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    response_data = response.json()
    document_id = response_data.pop("document_id")

    assert document_id > 0
    assert response_data == {
        "filename": "receipt.png",
        "content_type": "image/png",
        "size_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
    }

    stored_record = database_session.get(
        DocumentRecord,
        document_id,
    )

    assert stored_record is not None
    assert stored_record.filename == "receipt.png"
    assert stored_record.content_type == "image/png"
    assert stored_record.size_bytes == len(content)
    assert stored_record.sha256 == sha256(content).hexdigest()
    assert stored_record.created_at is not None

    stored_path = get_document_path(
        fingerprint=sha256(content).hexdigest(),
        content_type="image/png",
        storage_root=storage_root,
    )

    assert stored_path.exists()
    assert stored_path.read_bytes() == content

def test_reject_unsupported_document_type(
    client: TestClient,
) -> None:
    """A text file should be rejected."""
    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "notes.txt",
                b"not a supported document",
                "text/plain",
            )
        },
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "Unsupported file type. Use PDF, PNG, or JPEG."
    }


def test_reject_empty_document(
    client: TestClient,
) -> None:
    """An empty supported file should be rejected."""
    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "empty.pdf",
                b"",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The uploaded file is empty."
    }


def test_reject_oversized_document(
    client: TestClient,
) -> None:
    """A document exceeding the size limit should be rejected."""
    content = b"x" * (MAX_FILE_SIZE_BYTES + 1)

    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "large.pdf",
                content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "The uploaded file exceeds the 5 MB limit."
    }


def test_reject_content_that_does_not_match_declared_type(
    client: TestClient,
) -> None:
    """A fake PDF containing plain text should be rejected."""
    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "fake-invoice.pdf",
                b"This is plain text, not a PDF.",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "File content does not match its declared type."
    }


def test_reject_duplicate_document(
    client: TestClient,
    database_session: Session,
) -> None:
    """Uploading identical contents twice should return a conflict."""
    content = b"\x89PNG\r\n\x1a\n" + b"duplicate receipt"

    first_response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "receipt.png",
                content,
                "image/png",
            )
        },
    )

    second_response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "duplicate-receipt.png",
                content,
                "image/png",
            )
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "This document has already been uploaded."
    }

    stored_count = database_session.scalar(
        select(func.count()).select_from(DocumentRecord)
    )

    assert stored_count == 1