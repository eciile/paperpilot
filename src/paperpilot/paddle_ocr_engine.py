"""PaddleOCR implementation of the PaperPilot OCR interface."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol

from paperpilot.ocr_engine import (
    OcrEngineError,
    OcrLine,
    OcrOutput,
    build_ocr_output,
)


SUPPORTED_OCR_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
}


class PaddlePipeline(Protocol):
    """Minimal interface required from a PaddleOCR pipeline."""

    def predict(
        self,
        input_path: str,
    ) -> Iterable[object]:
        """Run OCR prediction for an image or PDF path."""
        ...


class PaddleOcrEngine:
    """Extract text using a lazily loaded PaddleOCR pipeline."""

    def __init__(
        self,
        *,
        language: str = "en",
        ocr_version: str = "PP-OCRv6",
        device: str = "cpu",
        pipeline: PaddlePipeline | None = None,
    ) -> None:
        """Configure the PaddleOCR adapter.

        Supplying a pipeline is mainly useful for automated tests. When no
        pipeline is supplied, PaddleOCR is imported and initialized only when
        extraction is requested for the first time.
        """
        self._language = language
        self._ocr_version = ocr_version
        self._device = device
        self._pipeline = pipeline

    @property
    def name(self) -> str:
        """Return the engine and model configuration identifier."""
        return (
            f"paddleocr:"
            f"{self._ocr_version}:"
            f"{self._language}"
        )

    def extract(
        self,
        document_path: Path,
        *,
        content_type: str,
    ) -> OcrOutput:
        """Extract normalized text from an image or PDF."""
        if content_type not in SUPPORTED_OCR_CONTENT_TYPES:
            raise OcrEngineError(
                f"Unsupported OCR content type: {content_type}"
            )

        if not document_path.is_file():
            raise OcrEngineError(
                f"OCR input file does not exist: {document_path}"
            )

        pipeline = self._get_pipeline()

        try:
            results = pipeline.predict(str(document_path))
            lines = _extract_lines(results)
        except OcrEngineError:
            raise
        except Exception as exc:
            raise OcrEngineError(
                "PaddleOCR could not process the document."
            ) from exc

        return build_ocr_output(lines)

    def _get_pipeline(self) -> PaddlePipeline:
        """Return the configured pipeline, loading PaddleOCR when needed."""
        if self._pipeline is not None:
            return self._pipeline

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrEngineError(
                "PaddleOCR is not installed. Install the PaperPilot "
                "OCR dependencies and a supported inference engine."
            ) from exc

        try:
            self._pipeline = PaddleOCR(
                lang=self._language,
                ocr_version=self._ocr_version,
                device=self._device,
                engine="paddle",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except Exception as exc:
            raise OcrEngineError(
                "PaddleOCR could not be initialized."
            ) from exc

        return self._pipeline


def _extract_lines(
    results: Iterable[object],
) -> list[OcrLine]:
    """Convert PaddleOCR page results into normalized OCR lines."""
    lines: list[OcrLine] = []

    for result in results:
        payload = _get_result_payload(result)

        texts = _as_list(
            payload.get("rec_texts"),
            field_name="rec_texts",
        )
        scores = _as_list(
            payload.get("rec_scores"),
            field_name="rec_scores",
        )

        if len(texts) != len(scores):
            raise OcrEngineError(
                "PaddleOCR returned different numbers of texts and scores."
            )

        for text, score in zip(texts, scores, strict=True):
            if not isinstance(text, str):
                raise OcrEngineError(
                    "PaddleOCR returned a non-text recognition value."
                )

            try:
                confidence = float(score)
                line = OcrLine(
                    text=text,
                    confidence=confidence,
                )
            except (TypeError, ValueError) as exc:
                raise OcrEngineError(
                    "PaddleOCR returned an invalid confidence value."
                ) from exc

            lines.append(line)

    return lines


def _get_result_payload(
    result: object,
) -> Mapping[str, Any]:
    """Return the useful JSON payload from one PaddleOCR result."""
    result_json = getattr(result, "json", None)

    if callable(result_json):
        result_json = result_json()

    if not isinstance(result_json, Mapping):
        raise OcrEngineError(
            "PaddleOCR returned a result without valid JSON data."
        )

    payload = result_json.get("res", result_json)

    if not isinstance(payload, Mapping):
        raise OcrEngineError(
            "PaddleOCR returned an invalid result payload."
        )

    return payload


def _as_list(
    value: object,
    *,
    field_name: str,
) -> list[object]:
    """Convert a PaddleOCR result collection into a Python list."""
    if value is None:
        return []

    if isinstance(value, (str, bytes, Mapping)):
        raise OcrEngineError(
            f"PaddleOCR returned an invalid {field_name} value."
        )

    try:
        return list(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise OcrEngineError(
            f"PaddleOCR returned an invalid {field_name} value."
        ) from exc