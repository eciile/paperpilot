"""Integration tests for structured extraction endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from paperpilot.models import (
    ExtractionResult,
    ExtractionStatus,
)


def upload_document(
    client: TestClient,
) -> int:
    """Upload a valid document and return its ID."""
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


def create_document_with_ocr(
    client: TestClient,
) -> int:
    """Upload a document and create a successful OCR result."""
    document_id = upload_document(client)

    response = client.post(
        f"/documents/{document_id}/ocr"
    )

    assert response.status_code == 201

    return document_id


def test_run_extraction_returns_persisted_success(
    client: TestClient,
    database_session: Session,
    structured_extractor,
) -> None:
    """Extraction should persist and return structured data."""
    document_id = create_document_with_ocr(client)

    response = client.post(
        f"/documents/{document_id}/extract"
    )

    assert response.status_code == 201

    data = response.json()

    assert data["extraction_result_id"] > 0
    assert data["document_id"] == document_id
    assert data["status"] == "succeeded"
    assert data["extractor"] == "stub-extractor"
    assert data["schema_version"] == "1.0"
    assert data["extracted_data"]["document_type"] == "invoice"
    assert (
        data["extracted_data"]["supplier_name"]
        == "Example Telecom"
    )
    assert data["extracted_data"]["currency"] == "EUR"
    assert data["extracted_data"]["total"] == "42.00"
    assert data["processing_time_ms"] >= 0
    assert data["error_message"] is None
    assert data["completed_at"] is not None
    assert structured_extractor.call_count == 1

    stored_result = database_session.get(
        ExtractionResult,
        data["extraction_result_id"],
    )

    assert stored_result is not None
    assert stored_result.status is ExtractionStatus.SUCCEEDED


def test_extraction_requires_successful_ocr(
    client: TestClient,
    structured_extractor,
) -> None:
    """Extraction without OCR should return HTTP 409."""
    document_id = upload_document(client)

    response = client.post(
        f"/documents/{document_id}/extract"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "A successful OCR result is required before extraction."
        )
    }
    assert structured_extractor.call_count == 0


def test_extraction_rejects_unknown_document(
    client: TestClient,
    structured_extractor,
) -> None:
    """An unknown document should return HTTP 404."""
    response = client.post("/documents/999/extract")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }
    assert structured_extractor.call_count == 0


def test_get_extraction_rejects_missing_result(
    client: TestClient,
) -> None:
    """A document without extraction should return HTTP 404."""
    document_id = create_document_with_ocr(client)

    response = client.get(
        f"/documents/{document_id}/extraction"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "No structured extraction result exists for this "
            "document."
        )
    }


def test_successful_extraction_prevents_reprocessing(
    client: TestClient,
    structured_extractor,
) -> None:
    """A successful result should block normal reprocessing."""
    document_id = create_document_with_ocr(client)

    first_response = client.post(
        f"/documents/{document_id}/extract"
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/documents/{document_id}/extract"
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": (
            "This document has already been extracted. "
            "Set allow_reprocess=true to create another attempt."
        )
    }
    assert structured_extractor.call_count == 1


def test_explicit_reprocessing_creates_new_result(
    client: TestClient,
    structured_extractor,
) -> None:
    """The reprocessing flag should create another attempt."""
    document_id = create_document_with_ocr(client)

    first_response = client.post(
        f"/documents/{document_id}/extract"
    )

    assert first_response.status_code == 201

    structured_extractor.total = "84.00"

    second_response = client.post(
        f"/documents/{document_id}/extract"
        "?allow_reprocess=true"
    )

    assert second_response.status_code == 201

    assert (
        first_response.json()["extraction_result_id"]
        != second_response.json()["extraction_result_id"]
    )
    assert (
        second_response.json()["extracted_data"]["total"]
        == "84.00"
    )
    assert structured_extractor.call_count == 2


def test_get_extraction_returns_latest_result(
    client: TestClient,
    structured_extractor,
) -> None:
    """The GET endpoint should return the newest attempt."""
    document_id = create_document_with_ocr(client)

    first_response = client.post(
        f"/documents/{document_id}/extract"
    )

    assert first_response.status_code == 201

    structured_extractor.total = "84.00"

    second_response = client.post(
        f"/documents/{document_id}/extract"
        "?allow_reprocess=true"
    )

    assert second_response.status_code == 201

    response = client.get(
        f"/documents/{document_id}/extraction"
    )

    assert response.status_code == 200
    assert (
        response.json()["extraction_result_id"]
        == second_response.json()["extraction_result_id"]
    )
    assert response.json()["extracted_data"]["total"] == "84.00"


def test_extraction_failure_is_persisted(
    client: TestClient,
    structured_extractor,
) -> None:
    """Extraction failures should be stored and reported."""
    document_id = create_document_with_ocr(client)

    structured_extractor.error_message = (
        "Simulated structured extraction failure."
    )

    response = client.post(
        f"/documents/{document_id}/extract"
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": (
            "Structured extraction failed: "
            "Simulated structured extraction failure."
        )
    }

    stored_response = client.get(
        f"/documents/{document_id}/extraction"
    )

    assert stored_response.status_code == 200

    data = stored_response.json()

    assert data["status"] == "failed"
    assert data["extracted_data"] is None
    assert (
        data["error_message"]
        == "Simulated structured extraction failure."
    )
    assert data["completed_at"] is not None