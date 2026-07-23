"""Optional smoke test for the real PaddleOCR engine."""

import os
from pathlib import Path

import pytest

from paperpilot.paddle_ocr_engine import PaddleOcrEngine


TEST_FILE_ENVIRONMENT_VARIABLE = (
    "PAPERPILOT_OCR_TEST_FILE"
)


def get_content_type(document_path: Path) -> str:
    """Return the supported content type for a test document."""
    suffix = document_path.suffix.lower()

    content_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }

    try:
        return content_types[suffix]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported OCR test file extension: {suffix}"
        ) from exc


@pytest.mark.skipif(
    not os.getenv(TEST_FILE_ENVIRONMENT_VARIABLE),
    reason=(
        "Set PAPERPILOT_OCR_TEST_FILE to run the "
        "real PaddleOCR smoke test."
    ),
)
def test_real_paddle_ocr_extracts_document() -> None:
    """Run the real OCR engine against a local document."""
    configured_path = os.environ[
        TEST_FILE_ENVIRONMENT_VARIABLE
    ]
    document_path = Path(configured_path)

    assert document_path.is_file()

    engine = PaddleOcrEngine()

    output = engine.extract(
        document_path,
        content_type=get_content_type(document_path),
    )

    assert isinstance(output.text, str)
    assert isinstance(output.lines, tuple)

    if output.average_confidence is not None:
        assert 0.0 <= output.average_confidence <= 1.0

    print("\nExtracted text:\n")
    print(output.text)