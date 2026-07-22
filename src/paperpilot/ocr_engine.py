"""Common interfaces and data structures for OCR engines."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


class OcrEngineError(RuntimeError):
    """Raised when an OCR engine cannot process a document."""


@dataclass(frozen=True, slots=True)
class OcrLine:
    """One line of text recognized by an OCR engine."""

    text: str
    confidence: float

    def __post_init__(self) -> None:
        """Validate OCR line values."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "OCR confidence must be between 0.0 and 1.0."
            )


@dataclass(frozen=True, slots=True)
class OcrOutput:
    """Normalized output returned by an OCR engine."""

    text: str
    average_confidence: float | None
    lines: tuple[OcrLine, ...]


@runtime_checkable
class OcrEngine(Protocol):
    """Interface implemented by PaperPilot OCR engines."""

    @property
    def name(self) -> str:
        """Return the stable name of the OCR engine."""
        ...

    def extract(
        self,
        document_path: Path,
        *,
        content_type: str,
    ) -> OcrOutput:
        """Extract text from a stored document."""
        ...


def build_ocr_output(
    lines: Iterable[OcrLine],
) -> OcrOutput:
    """Normalize OCR lines into a complete OCR output."""
    normalized_lines = tuple(
        line
        for line in lines
        if line.text.strip()
    )

    text = "\n".join(
        line.text.strip()
        for line in normalized_lines
    )

    average_confidence: float | None

    if normalized_lines:
        average_confidence = sum(
            line.confidence
            for line in normalized_lines
        ) / len(normalized_lines)
    else:
        average_confidence = None

    return OcrOutput(
        text=text,
        average_confidence=average_confidence,
        lines=normalized_lines,
    )