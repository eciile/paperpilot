from typing import Protocol
from pydantic import ValidationError
from paperpilot.extraction_schemas import FinancialDocumentExtractionV1
from paperpilot.extractor import ExtractionError

SYSTEM_PROMPT = """
Extract financial document data from OCR text using the required schema.

Rules:
- Use only information supported by the text; otherwise return null.
- Convert dates to YYYY-MM-DD and monetary values to numbers.
- Preserve document identifiers, including prefixes such as #.
- Match labelled subtotal, tax, and total values, not line-item prices.
- Return an ISO currency code only when explicit or clearly indicated by location
  and symbol, such as Singapore with $ meaning SGD.
- Do not include explanations or extra fields.
""".strip()

class StructuredModel(Protocol):
    "minimal structured_model interface required by the adapter"
    def invoke(
            self,
            input:object,
    ) -> object:
        """Invoke the structured model."""
        ...

class OllamaStructuredExtractor:
    """Extract validated financial data using a local ollama model."""
    def __init__(
            self,
            *,
            model_name:str = "qwen2.5:7b",
            base_url:str = "http://localhost:11434",
            structured_model: StructuredModel | None = None,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url
        self.structured_model = structured_model

    @property
    def name(self) -> str:
        """return the extractor configuration identifier"""
        return f"ollama:{self.model_name}"

    def extract(self, ocr_text: str) -> FinancialDocumentExtractionV1:
        """Extract validated financial data from OCR text."""
        normalized_text = ocr_text.strip()
        if not normalized_text:
            raise ExtractionError("OCR text is empty or whitespace only.")
        
        model = self._get_structured_model()

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human",("Extract structured information from this OCR text:\n\n"f"{normalized_text}")),
        ]

        try:
            raw_result = model.invoke(messages)
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError("Ollama could not extract structured document data.") from exc

        if isinstance(raw_result, FinancialDocumentExtractionV1):
            return raw_result

        try:
            return FinancialDocumentExtractionV1.model_validate(raw_result)
        except ValidationError as exc:
            raise ExtractionError("Ollama returned invalid structured extraction data.") from exc

    def _get_structured_model(self) -> StructuredModel:
        """return or lazily initialize the structured Ollama model."""
        if self.structured_model is not None:
            return self.structured_model

        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise ExtractionError(
                "LangChain Ollama is not installed. Install the "
                "PaperPilot extraction dependencies."
            ) from exc

        try:
            chat_model = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=0.0,
            )
            self.structured_model = (chat_model.with_structured_output(
                FinancialDocumentExtractionV1,
                method="json_schema"
                ))
        except Exception as exc:
            raise ExtractionError("Ollama structured model could not be initialized.") from exc

        return self.structured_model