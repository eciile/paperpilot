"""Tests for the PaperPilot database configuration."""

from sqlalchemy import create_engine, inspect

from paperpilot.database import initialize_database


def test_initialize_database_creates_documents_table() -> None:
    """Database initialization should create the documents table."""
    test_engine = create_engine("sqlite+pysqlite:///:memory:")

    initialize_database(test_engine)

    inspector = inspect(test_engine)

    assert "documents" in inspector.get_table_names()


def test_documents_table_contains_expected_columns() -> None:
    """The documents table should contain its required metadata columns."""
    test_engine = create_engine("sqlite+pysqlite:///:memory:")

    initialize_database(test_engine)

    inspector = inspect(test_engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("documents")
    }

    assert columns == {
        "id",
        "filename",
        "content_type",
        "size_bytes",
        "sha256",
        "created_at",
    }

def test_initialize_database_creates_ocr_results_table() -> None:
    """Database initialization should create the OCR results table."""
    test_engine = create_engine("sqlite+pysqlite:///:memory:")

    initialize_database(test_engine)

    inspector = inspect(test_engine)

    assert "ocr_results" in inspector.get_table_names()


def test_ocr_results_table_contains_expected_columns() -> None:
    """The OCR table should contain its processing fields."""
    test_engine = create_engine("sqlite+pysqlite:///:memory:")

    initialize_database(test_engine)

    inspector = inspect(test_engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("ocr_results")
    }

    assert columns == {
        "id",
        "document_id",
        "status",
        "engine",
        "text",
        "average_confidence",
        "processing_time_ms",
        "error_message",
        "created_at",
        "completed_at",
    }


def test_ocr_results_table_references_documents() -> None:
    """Each OCR result should reference an existing document."""
    test_engine = create_engine("sqlite+pysqlite:///:memory:")

    initialize_database(test_engine)

    inspector = inspect(test_engine)
    foreign_keys = inspector.get_foreign_keys("ocr_results")

    assert any(
        foreign_key["constrained_columns"] == ["document_id"]
        and foreign_key["referred_table"] == "documents"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in foreign_keys
    )