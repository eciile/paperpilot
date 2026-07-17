"""FastAPI application for PaperPilot."""

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from paperpilot.document_validation import (
    calculate_document_fingerprint,
    content_matches_type,
)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class StatusResponse(BaseModel):
    """Response returned by the status endpoint."""

    status: str
    service: str


class DocumentInspectionResponse(BaseModel):
    """Metadata returned after inspecting an uploaded document."""

    filename: str
    content_type: str
    size_bytes: int
    sha256: str


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


@app.post(
    "/documents/inspect",
    response_model=DocumentInspectionResponse,
)
async def inspect_document(
    file: Annotated[
        UploadFile,
        File(description="A PDF, PNG, or JPEG administrative document."),
    ],
) -> DocumentInspectionResponse:
    """Validate an uploaded document and return its basic metadata."""

    content_type = file.content_type or "application/octet-stream"

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Use PDF, PNG, or JPEG.",
        )

    contents = await file.read(MAX_FILE_SIZE_BYTES + 1)

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The uploaded file exceeds the 5 MB limit.",
        )

    if not content_matches_type(contents, content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match its declared type.",
        )

    return DocumentInspectionResponse(
        filename=file.filename or "unnamed",
        content_type=content_type,
        size_bytes=len(contents),
        sha256=calculate_document_fingerprint(contents),
    )