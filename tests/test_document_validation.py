"""Tests for document validation utilities."""

from paperpilot.document_validation import calculate_document_fingerprint


def test_identical_documents_have_identical_fingerprints() -> None:
    """Identical file contents should produce the same fingerprint."""
    content = b"same document contents"

    first = calculate_document_fingerprint(content)
    second = calculate_document_fingerprint(content)

    assert first == second


def test_different_documents_have_different_fingerprints() -> None:
    """Different file contents should produce different fingerprints."""
    first = calculate_document_fingerprint(b"first document")
    second = calculate_document_fingerprint(b"second document")

    assert first != second


def test_fingerprint_is_sha256_hexadecimal() -> None:
    """The generated fingerprint should contain 64 hexadecimal characters."""
    fingerprint = calculate_document_fingerprint(b"document")

    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)