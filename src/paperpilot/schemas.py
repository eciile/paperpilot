"""API response schemas for PaperPilot."""

from datetime import datetime

from pydantic import BaseModel

from paperpilot.models import DocumentRecord


class StatusResponse(BaseModel):
    """Response returned by the status endpoint."""

    status: str
    service: str


class DocumentInspectionResponse(BaseModel):
    """Metadata returned after accepting an uploaded document."""

    document_id: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str


class DocumentResponse(BaseModel):
    """A stored document catalog entry."""

    document_id: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime

    @classmethod
    def from_record(
        cls,
        record: DocumentRecord,
    ) -> "DocumentResponse":
        """Create an API response from a database record."""
        return cls(
            document_id=record.id,
            filename=record.filename,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            sha256=record.sha256,
            created_at=record.created_at,
        )


class DocumentListResponse(BaseModel):
    """A paginated collection of stored documents."""

    items: list[DocumentResponse]
    offset: int
    limit: int
    returned: int