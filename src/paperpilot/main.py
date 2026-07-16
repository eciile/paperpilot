"""FastAPI application for PaperPilot."""

from fastapi import FastAPI
from pydantic import BaseModel


class StatusResponse(BaseModel):
    """Response returned by the status endpoint."""

    status: str
    service: str


app = FastAPI(
    title="PaperPilot",
    version="0.1.0",
    description="API for the PaperPilot administrative document assistant.",
)


@app.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Return the current status of the PaperPilot API."""
    return StatusResponse(
        status="ok",
        service="paperpilot",
    )