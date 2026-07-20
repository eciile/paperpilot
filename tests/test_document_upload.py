"""Tests for basic document uploads."""

from fastapi.testclient import TestClient

from paperpilot.main import MAX_FILE_SIZE_BYTES, app
from hashlib import sha256
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from paperpilot.database import get_database_session
from paperpilot.models import Base, DocumentRecord

client = TestClient(app)

@pytest.fixture
def database_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory database session."""
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

    test_engine.dispose()


@pytest.fixture(autouse=True)
def override_database_session(
    database_session: Session,
) -> Generator[None, None, None]:
    """Make API requests use the isolated test database."""

    def get_test_session() -> Generator[Session, None, None]:
        yield database_session

    app.dependency_overrides[get_database_session] = get_test_session

    yield

    app.dependency_overrides.clear()

def test_inspect_png_document(database_session:Session,) -> None:
    """A supported PNG upload should return its metadata."""
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


def test_reject_unsupported_document_type() -> None:
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


def test_reject_empty_document() -> None:
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

def test_reject_oversized_document() -> None:
    """A document exceeding the size limit should be rejected."""
    content = b"x"*(MAX_FILE_SIZE_BYTES + 1)
    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "large.pdf",
                content,
                "application/pdf"
            )
        },
    )
    assert response.status_code == 413
    assert response.json() == {
        "detail": "The uploaded file exceeds the 5 MB limit."
    }
def test_reject_content_that_does_not_match_declared_type() -> None:
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