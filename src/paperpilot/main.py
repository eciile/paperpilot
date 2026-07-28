"""FastAPI application for PaperPilot."""

from pathlib import Path as FileSystemPath
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Path as PathParameter,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from paperpilot.database import get_database_session
from paperpilot.document_repository import (
    DuplicateDocumentError,
    get_document_by_id,
    list_document_records,
)
from paperpilot.document_service import (
    StoredDocumentMissingError,
    get_stored_document_path,
    register_document,
)
from paperpilot.document_storage import (
    DocumentStorageError,
    get_storage_root,
)
from paperpilot.document_validation import (
    calculate_document_fingerprint,
    content_matches_type,
)
from paperpilot.extraction_dependencies import (
    get_structured_extractor,
)
from paperpilot.extraction_repository import (
    get_latest_extraction_result,
)
from paperpilot.extraction_schemas import (
    FinancialDocumentExtractionV1,
)
from paperpilot.extraction_service import (
    ExtractionAlreadyProcessedError,
    ExtractionProcessingError,
    ExtractionProcessingInProgressError,
    NoSuccessfulOcrResultError,
    process_document_extraction,
)
from paperpilot.extractor import StructuredExtractor
from paperpilot.models import (
    ExtractionResult,
    OcrResult,
)
from paperpilot.ocr_dependencies import get_ocr_engine
from paperpilot.ocr_engine import OcrEngine
from paperpilot.ocr_repository import get_latest_ocr_result
from paperpilot.ocr_service import (
    OcrAlreadyProcessedError,
    OcrProcessingError,
    OcrProcessingInProgressError,
    process_document_ocr,
)
from paperpilot.schemas import (
    DocumentInspectionResponse,
    DocumentListResponse,
    DocumentResponse,
    ExtractionResultResponse,
    OcrResultResponse,
    StatusResponse,
)


ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


app = FastAPI(
    title="PaperPilot",
    version="0.1.0",
    description=(
        "API for the PaperPilot administrative document assistant."
    ),
)


def build_ocr_result_response(
    result: OcrResult,
) -> OcrResultResponse:
    """Convert a persisted OCR result into an API response."""
    return OcrResultResponse(
        ocr_result_id=result.id,
        document_id=result.document_id,
        status=result.status,
        engine=result.engine,
        text=result.text,
        average_confidence=result.average_confidence,
        processing_time_ms=result.processing_time_ms,
        error_message=result.error_message,
        created_at=result.created_at,
        completed_at=result.completed_at,
    )


def build_extraction_result_response(
    result: ExtractionResult,
) -> ExtractionResultResponse:
    """Convert an extraction record into an API response."""
    extracted_data = None

    if result.extracted_data is not None:
        extracted_data = (
            FinancialDocumentExtractionV1.model_validate(
                result.extracted_data
            )
        )

    return ExtractionResultResponse(
        extraction_result_id=result.id,
        document_id=result.document_id,
        ocr_result_id=result.ocr_result_id,
        status=result.status,
        extractor=result.extractor,
        schema_version=result.schema_version,
        extracted_data=extracted_data,
        processing_time_ms=result.processing_time_ms,
        error_message=result.error_message,
        created_at=result.created_at,
        completed_at=result.completed_at,
    )


@app.get(
    "/status",
    response_model=StatusResponse,
)
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
        File(
            description=(
                "A PDF, PNG, or JPEG administrative document."
            )
        ),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
    storage_root: Annotated[
        FileSystemPath,
        Depends(get_storage_root),
    ],
) -> DocumentInspectionResponse:
    """Validate, store, and register an uploaded document."""
    content_type = (
        file.content_type
        or "application/octet-stream"
    )

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Unsupported file type. Use PDF, PNG, or JPEG."
            ),
        )

    contents = await file.read(
        MAX_FILE_SIZE_BYTES + 1
    )

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "The uploaded file exceeds the 5 MB limit."
            ),
        )

    if not content_matches_type(
        contents,
        content_type,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "File content does not match its declared type."
            ),
        )

    fingerprint = calculate_document_fingerprint(
        contents
    )

    try:
        record = register_document(
            session,
            filename=file.filename,
            content_type=content_type,
            content=contents,
            fingerprint=fingerprint,
            storage_root=storage_root,
        )
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This document has already been uploaded."
            ),
        ) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="The document could not be stored.",
        ) from exc

    return DocumentInspectionResponse(
        document_id=record.id,
        filename=record.filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
    )


@app.get(
    "/documents",
    response_model=DocumentListResponse,
)
def get_documents(
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of documents to skip.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description=(
                "Maximum number of documents to return."
            ),
        ),
    ] = 20,
) -> DocumentListResponse:
    """Return a paginated page of stored documents."""
    records = list_document_records(
        session,
        offset=offset,
        limit=limit,
    )

    items = [
        DocumentResponse.from_record(record)
        for record in records
    ]

    return DocumentListResponse(
        items=items,
        offset=offset,
        limit=limit,
        returned=len(items),
    )


@app.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: Annotated[
        int,
        PathParameter(
            gt=0,
            description=(
                "Database ID of the requested document."
            ),
        ),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> DocumentResponse:
    """Return one stored document by ID."""
    record = get_document_by_id(
        session,
        document_id,
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return DocumentResponse.from_record(record)


@app.get(
    "/documents/{document_id}/download",
    response_class=FileResponse,
    responses={
        404: {
            "description": (
                "Document metadata was not found."
            ),
        },
        410: {
            "description": (
                "The stored document file is missing."
            ),
        },
    },
)
def download_document(
    document_id: Annotated[
        int,
        PathParameter(
            gt=0,
            description=(
                "Database ID of the document to download."
            ),
        ),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
    storage_root: Annotated[
        FileSystemPath,
        Depends(get_storage_root),
    ],
) -> FileResponse:
    """Download the original contents of a stored document."""
    record = get_document_by_id(
        session,
        document_id,
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    try:
        stored_path = get_stored_document_path(
            record,
            storage_root=storage_root,
        )
    except StoredDocumentMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "The stored document file is no longer "
                "available."
            ),
        ) from exc

    return FileResponse(
        path=stored_path,
        media_type=record.content_type,
        filename=record.filename,
    )


@app.post(
    "/documents/{document_id}/ocr",
    response_model=OcrResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {
            "description": "The document was not found.",
        },
        409: {
            "description": (
                "OCR is already running or the document "
                "was already processed."
            ),
        },
        410: {
            "description": (
                "The stored document file is missing."
            ),
        },
        500: {
            "description": "OCR processing failed.",
        },
    },
)
def run_document_ocr(
    document_id: Annotated[
        int,
        PathParameter(
            gt=0,
            description=(
                "Database ID of the document to process."
            ),
        ),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
    storage_root: Annotated[
        FileSystemPath,
        Depends(get_storage_root),
    ],
    ocr_engine: Annotated[
        OcrEngine,
        Depends(get_ocr_engine),
    ],
    allow_reprocess: Annotated[
        bool,
        Query(
            description=(
                "Create another OCR attempt even when a "
                "successful result already exists."
            ),
        ),
    ] = False,
) -> OcrResultResponse:
    """Run OCR on a stored document and persist the result."""
    document = get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    try:
        result = process_document_ocr(
            session,
            document=document,
            storage_root=storage_root,
            engine=ocr_engine,
            allow_reprocess=allow_reprocess,
        )
    except StoredDocumentMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "The stored document file is no longer "
                "available."
            ),
        ) from exc
    except OcrAlreadyProcessedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This document has already been processed "
                "with OCR. Set allow_reprocess=true to "
                "create another attempt."
            ),
        ) from exc
    except OcrProcessingInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OCR processing is already in progress.",
        ) from exc
    except OcrProcessingError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=f"OCR processing failed: {exc}",
        ) from exc

    return build_ocr_result_response(result)


@app.get(
    "/documents/{document_id}/ocr",
    response_model=OcrResultResponse,
    responses={
        404: {
            "description": (
                "The document or its OCR result was not found."
            ),
        },
    },
)
def read_document_ocr(
    document_id: Annotated[
        int,
        PathParameter(
            gt=0,
            description="Database ID of the document.",
        ),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> OcrResultResponse:
    """Return the latest OCR result for a document."""
    document = get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    result = get_latest_ocr_result(
        session,
        document_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No OCR result exists for this document."
            ),
        )

    return build_ocr_result_response(result)


@app.post(
    "/documents/{document_id}/extract",
    response_model=ExtractionResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {
            "description": "The document was not found.",
        },
        409: {
            "description": (
                "Successful OCR is missing, extraction is "
                "already running, or extraction already exists."
            ),
        },
        500: {
            "description": (
                "Structured extraction processing failed."
            ),
        },
    },
)
def run_document_extraction(
    document_id: Annotated[
        int,
        PathParameter(
            gt=0,
            description=(
                "Database ID of the document to extract."
            ),
        ),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
    extractor: Annotated[
        StructuredExtractor,
        Depends(get_structured_extractor),
    ],
    allow_reprocess: Annotated[
        bool,
        Query(
            description=(
                "Create another extraction attempt when a "
                "successful result already exists."
            ),
        ),
    ] = False,
) -> ExtractionResultResponse:
    """Extract structured data from a document's OCR text."""
    document = get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    try:
        result = process_document_extraction(
            session,
            document=document,
            extractor=extractor,
            allow_reprocess=allow_reprocess,
        )
    except NoSuccessfulOcrResultError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A successful OCR result is required before "
                "extraction."
            ),
        ) from exc
    except ExtractionAlreadyProcessedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This document has already been extracted. "
                "Set allow_reprocess=true to create another "
                "attempt."
            ),
        ) from exc
    except ExtractionProcessingInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Structured extraction is already in progress."
            ),
        ) from exc
    except ExtractionProcessingError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                f"Structured extraction failed: {exc}"
            ),
        ) from exc

    return build_extraction_result_response(result)


@app.get(
    "/documents/{document_id}/extraction",
    response_model=ExtractionResultResponse,
    responses={
        404: {
            "description": (
                "The document or extraction result was not found."
            ),
        },
    },
)
def read_document_extraction(
    document_id: Annotated[
        int,
        PathParameter(
            gt=0,
            description="Database ID of the document.",
        ),
    ],
    session: Annotated[
        Session,
        Depends(get_database_session),
    ],
) -> ExtractionResultResponse:
    """Return the newest extraction attempt for a document."""
    document = get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    result = get_latest_extraction_result(
        session,
        document_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No structured extraction result exists for "
                "this document."
            ),
        )

    return build_extraction_result_response(result)