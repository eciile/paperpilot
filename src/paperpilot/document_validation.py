"""Utilities for validating uploaded document contents."""
from hashlib import sha256

FILE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


def content_matches_type(content: bytes, content_type: str) -> bool:
    """Return whether file contents match the declared MIME type."""
    signatures = FILE_SIGNATURES.get(content_type)

    if signatures is None:
        return False

    return any(content.startswith(signature) for signature in signatures)

def calculate_document_fingerprint(content: bytes) -> str:
    """Return the SHA-256 hexadecimal fingerprint of document contents."""
    return sha256(content).hexdigest()