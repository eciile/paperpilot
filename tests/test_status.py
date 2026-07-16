"""Tests for the PaperPilot status endpoint."""

from fastapi.testclient import TestClient

from paperpilot.main import app


client = TestClient(app)


def test_status_endpoint() -> None:
    """The status endpoint should identify a running PaperPilot API."""
    response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "paperpilot",
    }