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