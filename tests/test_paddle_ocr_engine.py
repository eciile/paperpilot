"""Tests for the PaddleOCR engine adapter."""

from pathlib import Path

import pytest

from paperpilot.ocr_engine import (
    OcrEngine,
    OcrEngineError,
)
from paperpilot.paddle_ocr_engine import PaddleOcrEngine


class FakePaddleResult:
    """Test double representing one PaddleOCR result."""

    def __init__(
        self,
        *,
        texts: list[str],
        scores: list[float],
    ) -> None:
        """Create deterministic PaddleOCR-like JSON output."""
        self.json = {
            "res": {
                "rec_texts": texts,
                "rec_scores": scores,
            }
        }


class FakePaddlePipeline:
    """Test double for the PaddleOCR prediction pipeline."""

    def __init__(
        self,
        results: list[FakePaddleResult],
    ) -> None:
        """Configure prediction results."""
        self.results = results
        self.received_paths: list[str] = []

    def predict(
        self,
        input_path: str,
    ) -> list[FakePaddleResult]:
        """Return the configured results."""
        self.received_paths.append(input_path)
        return self.results


class FailingPaddlePipeline:
    """Pipeline that simulates an inference failure."""

    def predict(
        self,
        input_path: str,
    ) -> list[object]:
        """Raise an error instead of producing OCR output."""
        raise RuntimeError(
            f"Simulated inference failure for {input_path}"
        )


def create_document(
    tmp_path: Path,
    *,
    filename: str,
) -> Path:
    """Create a small file for adapter tests."""
    document_path = tmp_path / filename
    document_path.write_bytes(b"test document contents")

    return document_path


def test_paddle_engine_implements_ocr_protocol(
    tmp_path: Path,
) -> None:
    """The adapter should satisfy the common OCR protocol."""
    pipeline = FakePaddlePipeline(
        [
            FakePaddleResult(
                texts=["Invoice number: INV-42"],
                scores=[0.95],
            )
        ]
    )
    engine = PaddleOcrEngine(
        pipeline=pipeline,
    )

    assert isinstance(engine, OcrEngine)
    assert engine.name == "paddleocr:PP-OCRv6:en"

    document_path = create_document(
        tmp_path,
        filename="invoice.png",
    )

    output = engine.extract(
        document_path,
        content_type="image/png",
    )

    assert output.text == "Invoice number: INV-42"
    assert output.average_confidence == 0.95
    assert pipeline.received_paths == [
        str(document_path)
    ]


def test_paddle_engine_normalizes_image_results(
    tmp_path: Path,
) -> None:
    """Image OCR results should become normalized PaperPilot output."""
    pipeline = FakePaddlePipeline(
        [
            FakePaddleResult(
                texts=[
                    " Supplier: Example Telecom ",
                    "Total: 42.00 EUR",
                ],
                scores=[
                    0.90,
                    0.80,
                ],
            )
        ]
    )
    engine = PaddleOcrEngine(
        language="fr",
        pipeline=pipeline,
    )

    document_path = create_document(
        tmp_path,
        filename="invoice.jpg",
    )

    output = engine.extract(
        document_path,
        content_type="image/jpeg",
    )

    assert engine.name == "paddleocr:PP-OCRv6:fr"
    assert output.text == (
        "Supplier: Example Telecom\n"
        "Total: 42.00 EUR"
    )
    assert output.average_confidence == pytest.approx(0.85)
    assert len(output.lines) == 2


def test_paddle_engine_combines_pdf_pages(
    tmp_path: Path,
) -> None:
    """Results from multiple PDF pages should be combined in order."""
    pipeline = FakePaddlePipeline(
        [
            FakePaddleResult(
                texts=["Page one heading"],
                scores=[0.91],
            ),
            FakePaddleResult(
                texts=[
                    "Page two heading",
                    "Amount: 18.50 EUR",
                ],
                scores=[
                    0.89,
                    0.94,
                ],
            ),
        ]
    )
    engine = PaddleOcrEngine(
        pipeline=pipeline,
    )

    document_path = create_document(
        tmp_path,
        filename="invoice.pdf",
    )

    output = engine.extract(
        document_path,
        content_type="application/pdf",
    )

    assert output.text == (
        "Page one heading\n"
        "Page two heading\n"
        "Amount: 18.50 EUR"
    )
    assert output.average_confidence == pytest.approx(
        (0.91 + 0.89 + 0.94) / 3
    )
    assert len(output.lines) == 3


def test_paddle_engine_rejects_unsupported_type(
    tmp_path: Path,
) -> None:
    """Unsupported content types should fail before prediction."""
    pipeline = FakePaddlePipeline([])
    engine = PaddleOcrEngine(
        pipeline=pipeline,
    )

    document_path = create_document(
        tmp_path,
        filename="notes.txt",
    )

    with pytest.raises(
        OcrEngineError,
        match="Unsupported OCR content type",
    ):
        engine.extract(
            document_path,
            content_type="text/plain",
        )

    assert pipeline.received_paths == []


def test_paddle_engine_rejects_missing_file(
    tmp_path: Path,
) -> None:
    """A missing stored file should not reach PaddleOCR."""
    pipeline = FakePaddlePipeline([])
    engine = PaddleOcrEngine(
        pipeline=pipeline,
    )

    with pytest.raises(
        OcrEngineError,
        match="does not exist",
    ):
        engine.extract(
            tmp_path / "missing.pdf",
            content_type="application/pdf",
        )

    assert pipeline.received_paths == []


def test_paddle_engine_wraps_inference_failure(
    tmp_path: Path,
) -> None:
    """Unexpected PaddleOCR errors should become OcrEngineError."""
    engine = PaddleOcrEngine(
        pipeline=FailingPaddlePipeline(),
    )

    document_path = create_document(
        tmp_path,
        filename="invoice.png",
    )

    with pytest.raises(
        OcrEngineError,
        match="could not process",
    ):
        engine.extract(
            document_path,
            content_type="image/png",
        )


def test_paddle_engine_rejects_mismatched_texts_and_scores(
    tmp_path: Path,
) -> None:
    """Every recognized text should have one confidence value."""
    pipeline = FakePaddlePipeline(
        [
            FakePaddleResult(
                texts=[
                    "First line",
                    "Second line",
                ],
                scores=[0.90],
            )
        ]
    )
    engine = PaddleOcrEngine(
        pipeline=pipeline,
    )

    document_path = create_document(
        tmp_path,
        filename="invoice.png",
    )

    with pytest.raises(
        OcrEngineError,
        match="different numbers of texts and scores",
    ):
        engine.extract(
            document_path,
            content_type="image/png",
        )