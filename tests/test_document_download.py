"""Integration tests for downloading stored documents."""

from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from paperpilot.document_storage import get_document_path


def upload_png(
    client: TestClient,
    *,
    filename: str,
    content: bytes,
):
    """Upload a small valid PNG-like document."""
    return client.post(
        "/documents/inspect",
        files={
            "file": (
                filename,
                content,
                "image/png",
            )
        },
    )


def test_download_document_returns_original_contents(
    client: TestClient,
) -> None:
    """A downloaded document should match the original upload."""
    content = b"\x89PNG\r\n\x1a\n" + b"downloadable receipt"

    upload_response = upload_png(
        client,
        filename="../../private/receipt.png",
        content=content,
    )

    assert upload_response.status_code == 200

    upload_data = upload_response.json()
    document_id = upload_data["document_id"]

    assert upload_data["filename"] == "receipt.png"

    response = client.get(
        f"/documents/{document_id}/download"
    )

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"

    content_disposition = response.headers["content-disposition"]

    assert "attachment" in content_disposition
    assert 'filename="receipt.png"' in content_disposition
    assert ".." not in content_disposition


def test_download_unknown_document_returns_not_found(
    client: TestClient,
) -> None:
    """Downloading an unknown document should return HTTP 404."""
    response = client.get("/documents/999/download")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }


def test_download_missing_stored_file_returns_gone(
    client: TestClient,
    storage_root: Path,
) -> None:
    """Missing file contents should return HTTP 410."""
    content = b"\x89PNG\r\n\x1a\n" + b"file to remove"

    upload_response = upload_png(
        client,
        filename="temporary-receipt.png",
        content=content,
    )

    assert upload_response.status_code == 200

    upload_data = upload_response.json()
    document_id = upload_data["document_id"]
    fingerprint = sha256(content).hexdigest()

    stored_path = get_document_path(
        fingerprint=fingerprint,
        content_type="image/png",
        storage_root=storage_root,
    )

    assert stored_path.exists()

    stored_path.unlink()

    response = client.get(
        f"/documents/{document_id}/download"
    )

    assert response.status_code == 410
    assert response.json() == {
        "detail": (
            "The stored document file is no longer available."
        )
    }