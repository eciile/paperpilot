"""Integration tests for PaperPilot OCR endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from paperpilot.models import OcrResult, OcrStatus
from hashlib import sha256
from pathlib import Path

from paperpilot.document_storage import get_document_path

def upload_document(client: TestClient) -> int:
    """Upload a valid PNG and return its document ID."""
    content = b"\x89PNG\r\n\x1a\nexample invoice"

    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "invoice.png",
                content,
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    return response.json()["document_id"]


def test_run_ocr_returns_persisted_success(
    client: TestClient,
    database_session: Session,
    ocr_engine,
) -> None:
    """The OCR endpoint should persist and return extracted text."""
    document_id = upload_document(client)

    response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert response.status_code == 201

    data = response.json()

    assert data["ocr_result_id"] > 0
    assert data["document_id"] == document_id
    assert data["status"] == "succeeded"
    assert data["engine"] == "stub-ocr"
    assert data["text"] == "Invoice number: INV-42"
    assert data["average_confidence"] == 0.92
    assert data["processing_time_ms"] >= 0
    assert data["error_message"] is None
    assert data["created_at"] is not None
    assert data["completed_at"] is not None
    assert ocr_engine.call_count == 1

    stored_result = database_session.get(
        OcrResult,
        data["ocr_result_id"],
    )

    assert stored_result is not None
    assert stored_result.status is OcrStatus.SUCCEEDED
    assert stored_result.text == "Invoice number: INV-42"

def test_get_ocr_returns_latest_result(
    client: TestClient,
    ocr_engine,
) -> None:
    """The GET endpoint should return the latest OCR attempt."""
    document_id = upload_document(client)

    first_response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert first_response.status_code == 201

    ocr_engine.text = "Updated OCR result"
    ocr_engine.confidence = 0.97
    ocr_engine.name = "updated-stub-ocr"

    second_response = client.post(
        f"/documents/{document_id}/ocr"
        "?allow_reprocess=true"
    )

    assert second_response.status_code == 201

    response = client.get(
        f"/documents/{document_id}/ocr"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["ocr_result_id"]
        == second_response.json()["ocr_result_id"]
    )
    assert data["text"] == "Updated OCR result"
    assert data["average_confidence"] == 0.97
    assert data["engine"] == "updated-stub-ocr"

def test_run_ocr_rejects_unknown_document(
    client: TestClient,
    ocr_engine,
) -> None:
    """An unknown document should return HTTP 404."""
    response = client.post("/documents/999/ocr")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }
    assert ocr_engine.call_count == 0


def test_get_ocr_rejects_document_without_result(
    client: TestClient,
) -> None:
    """A document without OCR attempts should return HTTP 404."""
    document_id = upload_document(client)

    response = client.get(
        f"/documents/{document_id}/ocr"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "No OCR result exists for this document."
    }


def test_run_ocr_prevents_unintended_reprocessing(
    client: TestClient,
    ocr_engine,
) -> None:
    """A successful result should block normal reprocessing."""
    document_id = upload_document(client)

    first_response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": (
            "This document has already been processed with OCR. "
            "Set allow_reprocess=true to create another attempt."
        )
    }
    assert ocr_engine.call_count == 1


def test_run_ocr_allows_explicit_reprocessing(
    client: TestClient,
    ocr_engine,
) -> None:
    """The reprocessing flag should create another OCR attempt."""
    document_id = upload_document(client)

    first_response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert first_response.status_code == 201

    ocr_engine.text = "Second OCR result"

    second_response = client.post(
        f"/documents/{document_id}/ocr"
        "?allow_reprocess=true"
    )

    assert second_response.status_code == 201

    assert (
        first_response.json()["ocr_result_id"]
        != second_response.json()["ocr_result_id"]
    )
    assert second_response.json()["text"] == "Second OCR result"
    assert ocr_engine.call_count == 2


def test_run_ocr_returns_gone_when_file_is_missing(
    client: TestClient,
    storage_root: Path,
    ocr_engine,
) -> None:
    """Metadata without stored bytes should return HTTP 410."""
    content = b"\x89PNG\r\n\x1a\nmissing OCR source"

    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "missing.png",
                content,
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    document_id = response.json()["document_id"]

    stored_path = get_document_path(
        fingerprint=sha256(content).hexdigest(),
        content_type="image/png",
        storage_root=storage_root,
    )

    assert stored_path.exists()
    stored_path.unlink()

    response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert response.status_code == 410
    assert response.json() == {
        "detail": (
            "The stored document file is no longer available."
        )
    }
    assert ocr_engine.call_count == 0


def test_run_ocr_failure_is_persisted(
    client: TestClient,
    ocr_engine,
) -> None:
    """OCR failures should be persisted and reported."""
    document_id = upload_document(client)

    ocr_engine.error_message = (
        "Simulated OCR model failure."
    )

    response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": (
            "OCR processing failed: "
            "Simulated OCR model failure."
        )
    }

    stored_response = client.get(
        f"/documents/{document_id}/ocr"
    )

    assert stored_response.status_code == 200

    data = stored_response.json()

    assert data["status"] == "failed"
    assert data["text"] is None
    assert data["average_confidence"] is None
    assert (
        data["error_message"]
        == "Simulated OCR model failure."
    )
    assert data["completed_at"] is not None