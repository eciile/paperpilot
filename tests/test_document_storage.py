"""Tests for local document file storage."""

from hashlib import sha256
from pathlib import Path

import pytest

from paperpilot.document_storage import (
    DocumentIntegrityError,
    get_document_path,
    normalize_filename,
    store_document_content,
)


def test_normalize_filename_removes_directory_components() -> None:
    """Client directory components should not be retained."""
    assert normalize_filename(
        r"C:\fakepath\receipt.pdf"
    ) == "receipt.pdf"

    assert normalize_filename(
        "../../private/invoice.pdf"
    ) == "invoice.pdf"


def test_normalize_filename_handles_missing_filename() -> None:
    """Missing or empty filenames should use a safe fallback."""
    assert normalize_filename(None) == "document"
    assert normalize_filename("") == "document"
    assert normalize_filename("   ") == "document"


def test_get_document_path_uses_fingerprint(
    tmp_path: Path,
) -> None:
    """The storage path should be based on the document fingerprint."""
    fingerprint = "a" * 64

    path = get_document_path(
        fingerprint=fingerprint,
        content_type="application/pdf",
        storage_root=tmp_path,
    )

    assert path == (
        tmp_path
        / "aa"
        / f"{fingerprint}.pdf"
    )


def test_store_document_content_writes_document(
    tmp_path: Path,
) -> None:
    """Document contents should be written to their final path."""
    content = b"%PDF-example document"
    fingerprint = sha256(content).hexdigest()

    stored_path = store_document_content(
        content=content,
        fingerprint=fingerprint,
        content_type="application/pdf",
        storage_root=tmp_path,
    )

    assert stored_path.exists()
    assert stored_path.read_bytes() == content
    assert stored_path.name == f"{fingerprint}.pdf"
    assert stored_path.parent.name == fingerprint[:2]


def test_store_document_content_is_idempotent(
    tmp_path: Path,
) -> None:
    """Storing identical contents twice should use the same path."""
    content = b"\x89PNG\r\n\x1a\nexample image"
    fingerprint = sha256(content).hexdigest()

    first_path = store_document_content(
        content=content,
        fingerprint=fingerprint,
        content_type="image/png",
        storage_root=tmp_path,
    )
    second_path = store_document_content(
        content=content,
        fingerprint=fingerprint,
        content_type="image/png",
        storage_root=tmp_path,
    )

    assert first_path == second_path
    assert second_path.read_bytes() == content


def test_store_document_content_rejects_wrong_fingerprint(
    tmp_path: Path,
) -> None:
    """Contents that do not match the supplied hash should be rejected."""
    with pytest.raises(
        DocumentIntegrityError,
        match="do not match their fingerprint",
    ):
        store_document_content(
            content=b"%PDF-example document",
            fingerprint="a" * 64,
            content_type="application/pdf",
            storage_root=tmp_path,
        )

    assert list(tmp_path.rglob("*")) == []