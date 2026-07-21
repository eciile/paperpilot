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