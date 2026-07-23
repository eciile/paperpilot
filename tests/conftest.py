"""Shared pytest fixtures for PaperPilot tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from paperpilot.database import get_database_session
from paperpilot.main import app
from paperpilot.models import Base
from pathlib import Path
from paperpilot.document_storage import get_storage_root
from paperpilot.ocr_dependencies import get_ocr_engine
from paperpilot.ocr_engine import (
    OcrEngineError,
    OcrLine,
    OcrOutput,
    build_ocr_output,
)



class StubOcrEngine:
    """Configurable OCR engine used by API tests."""

    def __init__(self) -> None:
        """Create a successful deterministic OCR engine."""
        self.name = "stub-ocr"
        self.text = "Invoice number: INV-42"
        self.confidence = 0.92
        self.error_message: str | None = None
        self.call_count = 0

    def extract(
        self,
        document_path: Path,
        *,
        content_type: str,
    ) -> OcrOutput:
        """Return deterministic output or simulate a failure."""
        self.call_count += 1

        assert document_path.is_file()
        assert content_type in {
            "application/pdf",
            "image/png",
            "image/jpeg",
        }

        if self.error_message is not None:
            raise OcrEngineError(self.error_message)

        return build_ocr_output(
            [
                OcrLine(
                    text=self.text,
                    confidence=self.confidence,
                )
            ]
        )

@pytest.fixture
def ocr_engine() -> StubOcrEngine:
    """Provide a deterministic OCR engine for API tests."""
    return StubOcrEngine()

@pytest.fixture
def database_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory database session."""
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

    test_engine.dispose()

@pytest.fixture
def client(
    database_session: Session,
    storage_root: Path,
    ocr_engine: StubOcrEngine,
) -> Generator[TestClient, None, None]:
    """Provide an API client using isolated test resources."""

    def get_test_session() -> Generator[Session, None, None]:
        yield database_session

    def get_test_storage_root() -> Path:
        return storage_root

    def get_test_ocr_engine() -> StubOcrEngine:
        return ocr_engine

    app.dependency_overrides[get_database_session] = (
        get_test_session
    )
    app.dependency_overrides[get_storage_root] = (
        get_test_storage_root
    )
    app.dependency_overrides[get_ocr_engine] = (
        get_test_ocr_engine
    )

    test_client = TestClient(app)

    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()

@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    """Provide an isolated document storage directory."""
    return tmp_path / "documents"
