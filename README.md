## Current capabilities

PaperPilot currently supports:

- PDF, PNG, and JPEG upload validation
- Maximum upload size validation
- File-signature verification
- SHA-256 document fingerprints
- Duplicate-document rejection
- SQLite metadata persistence
- Paginated document listing
- Document retrieval by ID

Uploaded file contents are not stored yet. Only document metadata is
persisted.

## Local development

Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1