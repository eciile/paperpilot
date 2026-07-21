"""Integration tests for the document catalog API."""

import pytest
from fastapi.testclient import TestClient


def upload_png(
    client: TestClient,
    *,
    filename: str,
    unique_content: bytes,
):
    """Upload a small PNG-like document."""
    content = b"\x89PNG\r\n\x1a\n" + unique_content

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


def test_list_documents_returns_newest_first(
    client: TestClient,
) -> None:
    """The catalog should return documents newest first."""
    first_response = upload_png(
        client,
        filename="first.png",
        unique_content=b"first document",
    )
    second_response = upload_png(
        client,
        filename="second.png",
        unique_content=b"second document",
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    response = client.get("/documents")

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["offset"] == 0
    assert response_data["limit"] == 20
    assert response_data["returned"] == 2
    assert [
        item["filename"]
        for item in response_data["items"]
    ] == [
        "second.png",
        "first.png",
    ]


def test_list_documents_applies_pagination(
    client: TestClient,
) -> None:
    """The catalog should respect offset and limit."""
    for index in range(3):
        response = upload_png(
            client,
            filename=f"document-{index}.png",
            unique_content=f"document-{index}".encode(),
        )

        assert response.status_code == 200

    response = client.get(
        "/documents",
        params={
            "offset": 1,
            "limit": 1,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["offset"] == 1
    assert response_data["limit"] == 1
    assert response_data["returned"] == 1
    assert response_data["items"][0]["filename"] == "document-1.png"


def test_get_document_returns_catalog_record(
    client: TestClient,
) -> None:
    """A stored document should be retrievable by ID."""
    upload_response = upload_png(
        client,
        filename="invoice.png",
        unique_content=b"invoice document",
    )

    assert upload_response.status_code == 200

    document_id = upload_response.json()["document_id"]

    response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["document_id"] == document_id
    assert response_data["filename"] == "invoice.png"
    assert response_data["content_type"] == "image/png"
    assert response_data["created_at"] is not None


def test_get_unknown_document_returns_not_found(
    client: TestClient,
) -> None:
    """An unknown document ID should return HTTP 404."""
    response = client.get("/documents/999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }


@pytest.mark.parametrize(
    ("parameters", "invalid_field"),
    [
        ({"offset": -1}, "offset"),
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
    ],
)
def test_list_documents_rejects_invalid_pagination(
    client: TestClient,
    parameters: dict[str, int],
    invalid_field: str,
) -> None:
    """Invalid pagination values should return HTTP 422."""
    response = client.get(
        "/documents",
        params=parameters,
    )

    assert response.status_code == 422

    error_locations = [
        error["loc"]
        for error in response.json()["detail"]
    ]

    assert ["query", invalid_field] in error_locations

def test_document_catalog_workflow(
    client: TestClient,
) -> None:
    """The API should support a complete catalog workflow."""
    first_upload = upload_png(
        client,
        filename="electricity-bill.png",
        unique_content=b"electricity bill",
    )
    second_upload = upload_png(
        client,
        filename="internet-invoice.png",
        unique_content=b"internet invoice",
    )

    assert first_upload.status_code == 200
    assert second_upload.status_code == 200

    first_id = first_upload.json()["document_id"]
    second_id = second_upload.json()["document_id"]

    duplicate_response = upload_png(
        client,
        filename="duplicate-name.png",
        unique_content=b"electricity bill",
    )

    assert duplicate_response.status_code == 409

    list_response = client.get(
        "/documents",
        params={
            "offset": 0,
            "limit": 10,
        },
    )

    assert list_response.status_code == 200

    list_data = list_response.json()

    assert list_data["returned"] == 2
    assert [
        item["document_id"]
        for item in list_data["items"]
    ] == [
        second_id,
        first_id,
    ]

    detail_response = client.get(
        f"/documents/{first_id}"
    )

    assert detail_response.status_code == 200
    assert (
        detail_response.json()["filename"]
        == "electricity-bill.png"
    )

    missing_response = client.get("/documents/999")

    assert missing_response.status_code == 404