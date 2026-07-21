"""Tests for document database operations."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from paperpilot.document_repository import (
    DuplicateDocumentError,
    create_document_record,
    get_document_by_id,
    get_document_by_sha256,
    list_document_records,
)
from paperpilot.models import Base


@pytest.fixture
def test_engine() -> Generator[Engine, None, None]:
    """Provide an isolated in-memory database engine."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


def test_create_document_record_persists_metadata(
    test_engine: Engine,
) -> None:
    """Creating a record should persist its document metadata."""
    with Session(test_engine) as session:
        created_record = create_document_record(
            session,
            filename="electricity-bill.pdf",
            content_type="application/pdf",
            size_bytes=42_000,
            sha256="a" * 64,
        )
        created_id = created_record.id

    with Session(test_engine) as session:
        stored_record = get_document_by_id(session, created_id)

        assert stored_record is not None
        assert stored_record.filename == "electricity-bill.pdf"
        assert stored_record.content_type == "application/pdf"
        assert stored_record.size_bytes == 42_000
        assert stored_record.sha256 == "a" * 64
        assert stored_record.created_at is not None


def test_get_document_by_id_returns_none_for_unknown_id(
    test_engine: Engine,
) -> None:
    """Retrieving an unknown document ID should return None."""
    with Session(test_engine) as session:
        stored_record = get_document_by_id(session, 999)

    assert stored_record is None


def test_get_document_by_sha256_returns_matching_document(
    test_engine: Engine,
) -> None:
    """A document should be retrievable through its fingerprint."""
    with Session(test_engine) as session:
        created_record = create_document_record(
            session,
            filename="receipt.png",
            content_type="image/png",
            size_bytes=500,
            sha256="b" * 64,
        )

        stored_record = get_document_by_sha256(
            session,
            created_record.sha256,
        )

        assert stored_record is not None
        assert stored_record.id == created_record.id
        assert stored_record.filename == "receipt.png"


def test_list_document_records_applies_ordering_and_pagination(
    test_engine: Engine,
) -> None:
    """Documents should be returned newest first in pages."""
    with Session(test_engine) as session:
        for index, filename in enumerate(
            ["first.pdf", "second.pdf", "third.pdf"],
            start=1,
        ):
            create_document_record(
                session,
                filename=filename,
                content_type="application/pdf",
                size_bytes=index * 1_000,
                sha256=str(index) * 64,
            )

        first_page = list_document_records(
            session,
            offset=0,
            limit=2,
        )
        second_page = list_document_records(
            session,
            offset=2,
            limit=2,
        )

        assert [
            record.filename for record in first_page
        ] == [
            "third.pdf",
            "second.pdf",
        ]
        assert [
            record.filename for record in second_page
        ] == [
            "first.pdf",
        ]


def test_duplicate_fingerprint_raises_duplicate_error(
    test_engine: Engine,
) -> None:
    """A duplicate fingerprint should not create another record."""
    with Session(test_engine) as session:
        create_document_record(
            session,
            filename="original.pdf",
            content_type="application/pdf",
            size_bytes=1_000,
            sha256="c" * 64,
        )

        with pytest.raises(DuplicateDocumentError):
            create_document_record(
                session,
                filename="duplicate.pdf",
                content_type="application/pdf",
                size_bytes=1_000,
                sha256="c" * 64,
            )

        stored_records = list_document_records(session)

        assert len(stored_records) == 1
        assert stored_records[0].filename == "original.pdf"