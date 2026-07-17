"""Tests for basic document uploads."""

from fastapi.testclient import TestClient

from paperpilot.main import MAX_FILE_SIZE_BYTES, app
from hashlib import sha256

client = TestClient(app)


def test_inspect_png_document() -> None:
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
    assert response.json() == {
        "filename": "receipt.png",
        "content_type": "image/png",
        "size_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
    }


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