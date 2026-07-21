"""Local file storage operations for PaperPilot documents."""

import os
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile


CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

DEFAULT_STORAGE_ROOT = Path(
    os.getenv(
        "PAPERPILOT_STORAGE_DIR",
        "data/documents",
    )
)


class DocumentStorageError(Exception):
    """Base exception for document storage failures."""


class DocumentIntegrityError(DocumentStorageError):
    """Raised when document contents do not match their fingerprint."""


def get_storage_root() -> Path:
    """Return the configured document storage directory."""
    return DEFAULT_STORAGE_ROOT


def normalize_filename(filename: str | None) -> str:
    """Return a filename without client-supplied directory components."""
    if not filename:
        return "document"

    normalized = filename.replace("\\", "/")
    basename = normalized.rsplit("/", maxsplit=1)[-1].strip()

    return basename or "document"


def get_document_path(
    *,
    fingerprint: str,
    content_type: str,
    storage_root: Path,
) -> Path:
    """Return the content-addressed path for a document."""
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type)

    if extension is None:
        raise DocumentStorageError(
            f"Unsupported document content type: {content_type}"
        )

    if (
        len(fingerprint) != 64
        or any(
            character not in "0123456789abcdef"
            for character in fingerprint
        )
    ):
        raise DocumentStorageError(
            "Document fingerprint must be a SHA-256 hexadecimal value."
        )

    return (
        storage_root
        / fingerprint[:2]
        / f"{fingerprint}{extension}"
    )


def store_document_content(
    *,
    content: bytes,
    fingerprint: str,
    content_type: str,
    storage_root: Path,
) -> Path:
    """Store document contents and return their final path."""
    calculated_fingerprint = sha256(content).hexdigest()

    if calculated_fingerprint != fingerprint:
        raise DocumentIntegrityError(
            "Document contents do not match their fingerprint."
        )

    destination = get_document_path(
        fingerprint=fingerprint,
        content_type=content_type,
        storage_root=storage_root,
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():
        existing_fingerprint = sha256(
            destination.read_bytes()
        ).hexdigest()

        if existing_fingerprint != fingerprint:
            raise DocumentIntegrityError(
                "The stored document does not match its expected fingerprint."
            )

        return destination

    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="wb",
            prefix=".paperpilot-",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        temporary_path.replace(destination)

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()

    return destination