# OCR Bills - MVP Backend

This backend implements the MVP core loop:
1. User registers/logs in
2. Upload receipt -> async processing
3. Review parsed items -> user confirms
4. Dashboard queries stored transactions/items

## Local quickstart

### Prereqs
- Python 3.11+

### Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Run
```bash
uvicorn app.main:app --reload --port 8000
```

Backend base URL:
- `http://localhost:8000`

## Notes
- OCR is implemented as an adapter:
  - If `GOOGLE_VISION_API_KEY` is configured, it uses Google Vision.
  - Otherwise it attempts local Tesseract via `pytesseract` (requires the `tesseract` binary installed).
  - If neither is available, processing fails gracefully and the receipt remains in `error` state so the UI can offer manual entry.

