"""Tests for common OCR engine abstractions."""

from pathlib import Path

import pytest

from paperpilot.ocr_engine import (
    OcrEngine,
    OcrLine,
    OcrOutput,
    build_ocr_output,
)


class FakeOcrEngine:
    """Small OCR implementation used only for interface testing."""

    @property
    def name(self) -> str:
        """Return the fake engine name."""
        return "fake-ocr"

    def extract(
        self,
        document_path: Path,
        *,
        content_type: str,
    ) -> OcrOutput:
        """Return deterministic OCR output."""
        assert document_path.name == "invoice.png"
        assert content_type == "image/png"

        return build_ocr_output(
            [
                OcrLine(
                    text="Supplier: Example Telecom",
                    confidence=0.90,
                ),
                OcrLine(
                    text="Total: 42.00 EUR",
                    confidence=0.80,
                ),
            ]
        )


def test_build_ocr_output_combines_lines() -> None:
    """OCR lines should be combined into normalized document text."""
    output = build_ocr_output(
        [
            OcrLine(
                text=" Supplier: Example Telecom ",
                confidence=0.90,
            ),
            OcrLine(
                text="Total: 42.00 EUR",
                confidence=0.80,
            ),
        ]
    )

    assert output.text == (
        "Supplier: Example Telecom\n"
        "Total: 42.00 EUR"
    )
    assert output.average_confidence == pytest.approx(0.85)
    assert len(output.lines) == 2


def test_build_ocr_output_ignores_blank_lines() -> None:
    """Blank OCR lines should not appear in normalized output."""
    output = build_ocr_output(
        [
            OcrLine(
                text="",
                confidence=0.20,
            ),
            OcrLine(
                text="   ",
                confidence=0.30,
            ),
            OcrLine(
                text="Invoice number: INV-42",
                confidence=0.95,
            ),
        ]
    )

    assert output.text == "Invoice number: INV-42"
    assert output.average_confidence == 0.95
    assert len(output.lines) == 1


def test_build_empty_ocr_output() -> None:
    """No recognized lines should produce an empty OCR result."""
    output = build_ocr_output([])

    assert output.text == ""
    assert output.average_confidence is None
    assert output.lines == ()


@pytest.mark.parametrize(
    "confidence",
    [-0.01, 1.01],
)
def test_ocr_line_rejects_invalid_confidence(
    confidence: float,
) -> None:
    """Confidence values outside zero to one should be rejected."""
    with pytest.raises(
        ValueError,
        match="between 0.0 and 1.0",
    ):
        OcrLine(
            text="Invalid confidence",
            confidence=confidence,
        )


def test_fake_engine_implements_ocr_protocol(
    tmp_path: Path,
) -> None:
    """A structurally compatible engine should satisfy the protocol."""
    engine = FakeOcrEngine()

    assert isinstance(engine, OcrEngine)
    assert engine.name == "fake-ocr"

    output = engine.extract(
        tmp_path / "invoice.png",
        content_type="image/png",
    )

    assert output.text == (
        "Supplier: Example Telecom\n"
        "Total: 42.00 EUR"
    )
    assert output.average_confidence == pytest.approx(0.85)