"""FastAPI application for PaperPilot."""

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile, status, Depends
from pydantic import BaseModel
from paperpilot.database import (
    get_database_session,
    initialize_database,
)
from paperpilot.document_validation import (
    calculate_document_fingerprint,
    content_matches_type,
)
from paperpilot.document_repository import create_document_record
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session


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
    document_id: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize application resources."""
    initialize_database()
    yield


app = FastAPI(
    title="PaperPilot",
    version="0.1.0",
    description="API for the PaperPilot administrative document assistant.",
    lifespan=lifespan
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
    session: Annotated[
        Session,
        Depends(get_database_session),
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

    fingerprint = calculate_document_fingerprint(contents)
    record = create_document_record(
        session,
        filename=file.filename or"unnamed",
        content_type=content_type,
        size_bytes=len(contents),
        sha256=fingerprint,
    )
    return DocumentInspectionResponse(
        document_id=record.id,
        filename=record.filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
    )