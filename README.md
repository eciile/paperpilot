## Current capabilities

PaperPilot currently supports:

- PDF, PNG, and JPEG upload validation
- Maximum upload size validation
- File-signature verification
- SHA-256 document fingerprints
- Duplicate-document rejection
- SQLite metadata persistence
- Safe local storage of original document contents
- Content-addressed storage paths based on SHA-256 fingerprints
- Paginated document listing
- Document retrieval by ID
- Original document downloads

Uploaded files are stored locally. Client-provided filenames are retained only
as metadata and download names; they are never used as filesystem paths.

## Local development

Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1

## Document storage

By default, PaperPilot stores uploaded files under:

```text
data/documents/

## Starting Uvicorn

py -m pip install -e ".[dev]"
alembic upgrade head
uvicorn paperpilot.main:app --reload

## OCR processing

PaperPilot can run OCR on stored PDF, PNG, and JPEG documents.

The OCR feature uses PaddleOCR through an internal engine abstraction. Standard
automated tests use fake OCR engines and do not download or load real models.

### Install OCR dependencies

Install a compatible PaddlePaddle runtime for your operating system and hardware,
then install PaperPilot's optional OCR dependencies:

```powershell
py -m pip install -e ".[dev,ocr]"
```

Apply database migrations before starting the application:

```powershell
alembic upgrade head
uvicorn paperpilot.main:app --reload
```

### Run OCR

Upload a document first:

```http
POST /documents/inspect
```

Then process it:

```http
POST /documents/{document_id}/ocr
```

To explicitly create another OCR attempt:

```http
POST /documents/{document_id}/ocr?allow_reprocess=true
```

Retrieve the latest OCR result:

```http
GET /documents/{document_id}/ocr
```

OCR processing currently runs synchronously, so the POST request remains open
until processing succeeds or fails.

### Run the optional real OCR smoke test

Set the path to a local PDF or image:

```powershell
$env:PAPERPILOT_OCR_TEST_FILE = "C:\documents\invoice.png"
```

Run only the smoke test:

```powershell
py -m pytest tests/integration/test_paddle_ocr_smoke.py -v -s
```

Remove the environment variable afterward:

```powershell
Remove-Item Env:PAPERPILOT_OCR_TEST_FILE
```