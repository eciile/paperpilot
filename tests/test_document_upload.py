"""Tests for basic document uploads."""

from fastapi.testclient import TestClient

from paperpilot.main import MAX_FILE_SIZE_BYTES, app


client = TestClient(app)


def test_inspect_png_document() -> None:
    """A supported PNG upload should return its metadata."""
    content = b"example image content"

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
