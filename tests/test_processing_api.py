"""Integration tests for one-click document processing."""

from fastapi.testclient import TestClient


def upload_document(client: TestClient) -> int:
    """Upload a valid PNG and return its document ID."""
    response = client.post(
        "/documents/inspect",
        files={
            "file": (
                "invoice.png",
                b"\x89PNG\r\n\x1a\ncombined processing test",
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    return response.json()["document_id"]


def test_process_document_runs_ocr_and_extraction(
    client: TestClient,
    ocr_engine,
    structured_extractor,
) -> None:
    """One request should run the complete processing workflow."""
    document_id = upload_document(client)

    response = client.post(
        f"/documents/{document_id}/process"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["document_id"] == document_id

    assert data["ocr"]["status"] == "succeeded"
    assert data["ocr"]["text"] == "Invoice number: INV-42"

    assert data["extraction"]["status"] == "succeeded"
    assert (
        data["extraction"]["extracted_data"]["supplier_name"]
        == "Example Telecom"
    )
    assert (
        data["extraction"]["extracted_data"]["total"]
        == "42.00"
    )

    assert ocr_engine.call_count == 1
    assert structured_extractor.call_count == 1


def test_process_document_reuses_successful_results(
    client: TestClient,
    ocr_engine,
    structured_extractor,
) -> None:
    """Repeated processing should reuse completed results."""
    document_id = upload_document(client)

    first_response = client.post(
        f"/documents/{document_id}/process"
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/documents/{document_id}/process"
    )

    assert second_response.status_code == 200

    first_data = first_response.json()
    second_data = second_response.json()

    assert (
        second_data["ocr"]["ocr_result_id"]
        == first_data["ocr"]["ocr_result_id"]
    )
    assert (
        second_data["extraction"]["extraction_result_id"]
        == first_data["extraction"]["extraction_result_id"]
    )

    assert ocr_engine.call_count == 1
    assert structured_extractor.call_count == 1


def test_process_unknown_document_returns_not_found(
    client: TestClient,
    ocr_engine,
    structured_extractor,
) -> None:
    """An unknown document should return HTTP 404."""
    response = client.post("/documents/999/process")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }

    assert ocr_engine.call_count == 0
    assert structured_extractor.call_count == 0