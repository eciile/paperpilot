"""Tests for the OCR processing service."""

from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from paperpilot.document_service import (
    StoredDocumentMissingError,
    register_document,
)
from paperpilot.document_storage import get_document_path
from paperpilot.models import OcrResult, OcrStatus
from paperpilot.ocr_engine import (
    OcrEngineError,
    OcrLine,
    OcrOutput,
    build_ocr_output,
)
from paperpilot.ocr_repository import get_latest_ocr_result
from paperpilot.ocr_service import (
    OcrAlreadyProcessedError,
    OcrProcessingError,
    OcrProcessingInProgressError,
    process_document_ocr,
)


class SuccessfulOcrEngine:
    """Deterministic OCR engine used in service tests."""

    def __init__(
        self,
        *,
        text: str = "Invoice number: INV-42",
        confidence: float = 0.92,
        name: str = "fake-ocr",
    ) -> None:
        """Configure deterministic OCR output."""
        self._text = text
        self._confidence = confidence
        self._name = name
        self.call_count = 0

    @property
    def name(self) -> str:
        """Return the fake engine name."""
        return self._name

    def extract(
        self,
        document_path: Path,
        *,
        content_type: str,
    ) -> OcrOutput:
        """Return deterministic OCR output."""
        self.call_count += 1

        assert document_path.is_file()
        assert content_type in {
            "application/pdf",
            "image/png",
            "image/jpeg",
        }

        return build_ocr_output(
            [
                OcrLine(
                    text=self._text,
                    confidence=self._confidence,
                )
            ]
        )


class FailingOcrEngine:
    """OCR engine that always fails."""

    @property
    def name(self) -> str:
        """Return the fake engine name."""
        return "failing-ocr"

    def extract(
        self,
        document_path: Path,
        *,
        content_type: str,
    ) -> OcrOutput:
        """Simulate an OCR engine failure."""
        raise OcrEngineError(
            "Simulated OCR inference failure."
        )


def create_stored_document(
    database_session: Session,
    storage_root: Path,
):
    """Create one stored PDF document for OCR tests."""
    content = b"%PDF-example invoice"
    fingerprint = sha256(content).hexdigest()

    return register_document(
        database_session,
        filename="invoice.pdf",
        content_type="application/pdf",
        content=content,
        fingerprint=fingerprint,
        storage_root=storage_root,
    )


def test_process_document_ocr_persists_success(
    database_session: Session,
    storage_root: Path,
) -> None:
    """Successful OCR should persist its normalized output."""
    document = create_stored_document(
        database_session,
        storage_root,
    )
    engine = SuccessfulOcrEngine()

    result = process_document_ocr(
        database_session,
        document=document,
        storage_root=storage_root,
        engine=engine,
    )

    assert engine.call_count == 1
    assert result.status is OcrStatus.SUCCEEDED
    assert result.engine == "fake-ocr"
    assert result.text == "Invoice number: INV-42"
    assert result.average_confidence == 0.92
    assert result.processing_time_ms is not None
    assert result.processing_time_ms >= 0
    assert result.error_message is None
    assert result.completed_at is not None

    database_session.expire_all()

    stored_result = database_session.get(
        OcrResult,
        result.id,
    )

    assert stored_result is not None
    assert stored_result.status is OcrStatus.SUCCEEDED
    assert stored_result.text == "Invoice number: INV-42"


def test_process_document_ocr_persists_failure(
    database_session: Session,
    storage_root: Path,
) -> None:
    """An OCR failure should remain visible in the database."""
    document = create_stored_document(
        database_session,
        storage_root,
    )

    with pytest.raises(
        OcrProcessingError,
        match="Simulated OCR inference failure",
    ):
        process_document_ocr(
            database_session,
            document=document,
            storage_root=storage_root,
            engine=FailingOcrEngine(),
        )

    latest_result = get_latest_ocr_result(
        database_session,
        document.id,
    )

    assert latest_result is not None
    assert latest_result.status is OcrStatus.FAILED
    assert latest_result.text is None
    assert latest_result.average_confidence is None
    assert (
        latest_result.error_message
        == "Simulated OCR inference failure."
    )
    assert latest_result.processing_time_ms is not None
    assert latest_result.completed_at is not None


def test_successful_result_prevents_unintended_reprocessing(
    database_session: Session,
    storage_root: Path,
) -> None:
    """A completed OCR result should block another normal attempt."""
    document = create_stored_document(
        database_session,
        storage_root,
    )

    first_engine = SuccessfulOcrEngine()
    second_engine = SuccessfulOcrEngine(
        name="second-fake-ocr",
    )

    process_document_ocr(
        database_session,
        document=document,
        storage_root=storage_root,
        engine=first_engine,
    )

    with pytest.raises(
        OcrAlreadyProcessedError,
        match="already been processed",
    ):
        process_document_ocr(
            database_session,
            document=document,
            storage_root=storage_root,
            engine=second_engine,
        )

    assert first_engine.call_count == 1
    assert second_engine.call_count == 0

    stored_count = database_session.scalar(
        select(func.count()).select_from(OcrResult)
    )

    assert stored_count == 1


def test_explicit_reprocessing_creates_new_attempt(
    database_session: Session,
    storage_root: Path,
) -> None:
    """Explicit reprocessing should preserve both OCR attempts."""
    document = create_stored_document(
        database_session,
        storage_root,
    )

    first_result = process_document_ocr(
        database_session,
        document=document,
        storage_root=storage_root,
        engine=SuccessfulOcrEngine(
            text="First OCR result",
            name="first-engine",
        ),
    )

    second_result = process_document_ocr(
        database_session,
        document=document,
        storage_root=storage_root,
        engine=SuccessfulOcrEngine(
            text="Second OCR result",
            name="second-engine",
        ),
        allow_reprocess=True,
    )

    assert first_result.id != second_result.id
    assert second_result.text == "Second OCR result"
    assert second_result.engine == "second-engine"

    stored_count = database_session.scalar(
        select(func.count()).select_from(OcrResult)
    )

    assert stored_count == 2

    latest_result = get_latest_ocr_result(
        database_session,
        document.id,
    )

    assert latest_result is not None
    assert latest_result.id == second_result.id


def test_active_attempt_prevents_parallel_processing(
    database_session: Session,
    storage_root: Path,
) -> None:
    """An active OCR attempt should block another attempt."""
    document = create_stored_document(
        database_session,
        storage_root,
    )

    active_result = OcrResult(
        document_id=document.id,
        engine="active-engine",
        status=OcrStatus.PROCESSING,
    )

    database_session.add(active_result)
    database_session.commit()

    engine = SuccessfulOcrEngine()

    with pytest.raises(
        OcrProcessingInProgressError,
        match="already in progress",
    ):
        process_document_ocr(
            database_session,
            document=document,
            storage_root=storage_root,
            engine=engine,
            allow_reprocess=True,
        )

    assert engine.call_count == 0


def test_missing_stored_file_does_not_create_ocr_attempt(
    database_session: Session,
    storage_root: Path,
) -> None:
    """OCR should fail before creating an attempt when bytes are missing."""
    document = create_stored_document(
        database_session,
        storage_root,
    )

    stored_path = get_document_path(
        fingerprint=document.sha256,
        content_type=document.content_type,
        storage_root=storage_root,
    )
    stored_path.unlink()

    with pytest.raises(StoredDocumentMissingError):
        process_document_ocr(
            database_session,
            document=document,
            storage_root=storage_root,
            engine=SuccessfulOcrEngine(),
        )

    stored_count = database_session.scalar(
        select(func.count()).select_from(OcrResult)
    )

    assert stored_count == 0