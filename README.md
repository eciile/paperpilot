# PaperPilot

PaperPilot is a privacy-focused API for storing, processing, and extracting
structured information from administrative documents such as invoices,
receipts, and utility bills.

Documents and their processing results are stored locally. Automated tests use
isolated databases, temporary storage directories, and fake AI engines, so they
do not require PaddleOCR, Ollama, or downloaded models.

## Current capabilities

PaperPilot currently supports:

### Document management

- PDF, PNG, and JPEG uploads
- Maximum upload-size validation
- File-signature verification
- SHA-256 document fingerprints
- Duplicate-document rejection
- SQLite metadata persistence
- Safe local storage of original document contents
- Content-addressed storage paths
- Paginated document listing
- Document metadata retrieval by ID
- Original document downloads

### OCR processing

- OCR processing for stored PDF, PNG, and JPEG documents
- PaddleOCR integration through an engine abstraction
- Persisted OCR text, confidence, status, engine, and processing time
- Successful and failed OCR attempt history
- Protection against accidental repeated processing
- Explicit OCR reprocessing
- Retrieval of the latest OCR result

### Structured extraction

- Structured extraction from successful OCR text
- Local Ollama integration through LangChain
- Versioned and validated Pydantic output
- Invoice, receipt, utility-bill, and unknown document classification
- Extraction of supplier, document number, dates, currency, tax, and totals
- Persisted successful and failed extraction attempts
- Protection against accidental repeated extraction
- Explicit re-extraction
- Retrieval of the latest extraction result

## Requirements

- Python 3.11 or newer
- Git
- PaddlePaddle and PaddleOCR for real OCR processing
- Ollama and a compatible local model for real structured extraction

The standard automated test suite does not require PaddleOCR or Ollama.

## Local development

### 1. Create a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install development dependencies

```powershell
py -m pip install --upgrade pip
py -m pip install -e ".[dev]"
```

### 3. Apply database migrations

```powershell
alembic upgrade head
```

### 4. Start the API

```powershell
uvicorn paperpilot.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive Swagger documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## Document storage

By default, uploaded files are stored under:

```text
data/documents/
```

PaperPilot uses content-addressed paths derived from each document's SHA-256
fingerprint:

```text
data/documents/
└── a4/
    └── a421...full-sha256-fingerprint....pdf
```

Client-provided filenames are retained only as metadata and download names. They
are never used directly as filesystem paths.

For example, a submitted filename such as:

```text
../../private/invoice.pdf
```

is normalised to:

```text
invoice.pdf
```

The storage directory can be changed with the
`PAPERPILOT_STORAGE_DIR` environment variable:

```powershell
$env:PAPERPILOT_STORAGE_DIR = "C:\paperpilot-storage"
uvicorn paperpilot.main:app --reload
```

Local database files and uploaded documents are excluded from Git.

## API overview

### Service status

```http
GET /status
```

### Upload and inspect a document

```http
POST /documents/inspect
```

### List stored documents

```http
GET /documents?offset=0&limit=20
```

### Retrieve document metadata

```http
GET /documents/{document_id}
```

### Download the original document

```http
GET /documents/{document_id}/download
```

Possible download responses include:

- `200 OK` — the original document is returned
- `404 Not Found` — no document metadata exists
- `410 Gone` — metadata exists, but the stored file is missing

## OCR processing

PaperPilot runs OCR through an internal engine interface. The current real
implementation uses PaddleOCR.

OCR processing currently runs synchronously. The request remains open until
processing succeeds or fails.

### Install OCR dependencies

Install a compatible PaddlePaddle runtime for your operating system and
hardware, then install PaperPilot's optional OCR dependencies:

```powershell
py -m pip install -e ".[dev,ocr]"
```

### Run OCR

Upload a document first:

```http
POST /documents/inspect
```

Run OCR on the stored document:

```http
POST /documents/{document_id}/ocr
```

Explicitly create another OCR attempt:

```http
POST /documents/{document_id}/ocr?allow_reprocess=true
```

Retrieve the latest OCR result:

```http
GET /documents/{document_id}/ocr
```

An OCR result contains:

- Processing status
- OCR engine identifier
- Extracted text
- Average confidence
- Processing duration
- Failure information, when applicable
- Creation and completion timestamps

## Structured extraction

PaperPilot can convert successful OCR text into validated financial-document
data.

The version 1 extraction schema supports:

- Document type
- Supplier or merchant name
- Document number
- Issue date
- Due date
- Currency
- Subtotal
- Tax
- Total

Missing information is returned as `null`. Unexpected fields and invalid values
are rejected before the result is persisted.

### Install extraction dependencies

```powershell
py -m pip install -e ".[dev,extraction]"
```

Ensure Ollama is running and that the configured model is available locally.

### Run structured extraction

A successful OCR result must exist first:

```http
POST /documents/{document_id}/ocr
```

Run extraction:

```http
POST /documents/{document_id}/extract
```

Explicitly create another extraction attempt:

```http
POST /documents/{document_id}/extract?allow_reprocess=true
```

Retrieve the latest extraction result:

```http
GET /documents/{document_id}/extraction
```

## Automated tests

Run the complete test suite:

```powershell
python -m pytest
```

Run additional project checks:

```powershell
alembic check
git diff --check
```

Standard tests use:

- An isolated in-memory SQLite database
- Temporary document storage
- A fake OCR engine
- A fake structured extractor

They do not download models or contact Ollama.

## Optional real OCR smoke test

Install the OCR dependencies and set the path to a local PDF or image:

```powershell
$env:PAPERPILOT_OCR_TEST_FILE = "C:\documents\invoice.png"
```

Run the smoke test:

```powershell
python -m pytest `
  tests/integration/test_paddle_ocr_smoke.py `
  -v -s
```

Remove the environment variable afterward:

```powershell
Remove-Item Env:PAPERPILOT_OCR_TEST_FILE
```

## Optional real Ollama smoke test

Ensure Ollama is running and the configured model is available.

Set the smoke-test variables:

```powershell
$env:PAPERPILOT_OLLAMA_SMOKE = "1"
$env:PAPERPILOT_OLLAMA_MODEL = "qwen2.5:7b"
```

Run the smoke test:

```powershell
python -m pytest `
  tests/integration/test_ollama_extraction_smoke.py `
  -v -s
```

Remove the variables afterward:

```powershell
Remove-Item Env:PAPERPILOT_OLLAMA_SMOKE
Remove-Item Env:PAPERPILOT_OLLAMA_MODEL
```

## Database migrations

PaperPilot uses Alembic to manage database schema changes.

Apply all migrations:

```powershell
alembic upgrade head
```

Display the current migration:

```powershell
alembic current
```

Check whether the SQLAlchemy models require a new migration:

```powershell
alembic check
```

## Processing workflow

```text
Upload document
    ↓
Validate type, size, and signature
    ↓
Calculate SHA-256 fingerprint
    ↓
Store metadata and original file
    ↓
Run OCR
    ↓
Persist OCR text and processing metadata
    ↓
Run structured extraction
    ↓
Validate and persist financial document data
```