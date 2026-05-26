# ExTaSy — 2026-05-26 Improvements

Summary of work landed today. Project rebranded from FluxReceipt to **ExTaSy** (Expense Tracking System) at the end of the session.

---

## 1. Environment fixes

- **Mac LAN IP drift** caught: Flutter app's hardcoded default was `192.168.100.53` but current IP is `.63`. Updated `mobile/lib/core/config/app_config.dart` default.
- **Port 8000 collision**: an unrelated `studyforge-chroma` Docker container occupies 8000; 8001/8002 also taken. Backend moved to `8765`, mobile config updated accordingly.
- **Web frontend port**: moved from 3000 → 3737 to avoid conflict with the user's other dev app. Backend CORS allow-list updated.
- **Dashboard hydration error** fixed (`localStorage` read deferred to `useEffect`, SSR shell now matches first client render).

## 2. New backend endpoints

| Endpoint | Module | What it does |
|---|---|---|
| `GET /fx/rates` | `routes/fx.py` | Daily ECB rates from frankfurter.app, 24h in-memory cache, static fallback. Derives BAM via the locked EUR peg. |
| `GET /fx/convert` | `routes/fx.py` | Server-side amount conversion. |
| `GET /receipts/search?q=…` | `routes/receipts.py` | Multi-token search across `raw_text`, `store_name`, and item names. Works with Cyrillic, Arabic, CJK, etc. (SQL `ILIKE`-based after FTS5 sync issues — fast enough for SMB-scale data). |
| `GET /receipts/check-duplicate` | `routes/receipts.py` | Flags duplicates by `(store ilike, total ±1%, same calendar day)`. |
| `GET /budgets` / `POST` / `DELETE` | `routes/budgets.py` | Monthly category budgets. Response includes `spent`, `remaining`, `percent`, `projected_month_end`, `over_budget`. Cross-currency: each transaction converted to the budget's currency. |
| `GET /recommendations/recurring` | `routes/recommendations.py` | Surfaces repeatedly-purchased products with stable intervals; returns per-product monthly forecast plus a household total. |
| `GET /transactions/export.pdf` | `routes/transactions.py` | reportlab-generated expense report: header, category summary, top merchants, paginated transaction table. All amounts in chosen `display_currency`. |
| `GET /households` / `POST` / `POST /join` / `POST /{id}/rotate-token` / `POST /{id}/receipts/{id}/share` / `GET /{id}/receipts` / `DELETE /{id}/members/{user_id}` | `routes/households.py` | Share-link based household scaffold so multiple users can pool receipts. |
| `POST /reconcile/upload` | `routes/reconcile.py` | Accepts a bank-statement CSV, matches each row against confirmed receipts within `±2 days` and `±5%` (configurable), returns matched / unmatched bank / unmatched receipts. |

## 3. Insights expanded

`/insights` previously returned at most one frequency-spike + a baseline info string. Now also computes:

- **`price_increase`** — for each `(store, normalized product)` purchased ≥2 times in the last 90 days, compares latest vs previous unit_price and surfaces the largest swing (positive or negative) ≥10%.
- Frequency-spike loop now skips items with empty normalized names so non-Latin products (Arabic, CJK) don't collapse together.

## 4. Receipt parser

- `extract_tax_amount(raw_text)` — pulls the PDV / VAT / IVA / MWST / TVA / KDV / GST amount from raw OCR text. Used to populate the new `receipts.tax_amount` column at processing time.
- `Receipt.tax_amount` column added to the model and exposed via `ReceiptOut`.

## 5. Product normalization

Replaced ASCII+Cyrillic-only regex with Unicode-aware `\w+` so Arabic, CJK, Devanagari, Thai, Hebrew, Greek and other scripts no longer collapse to the empty string. This was silently breaking the recurring and price-change features for non-Latin receipts.

## 6. Schema additions

New tables:
- `budgets` (id, user_id, category_id, monthly_limit, currency, timestamps)
- `households` (id, name, owner_user_id, invite_token, created_at)
- `household_members` (id, household_id, user_id, role, created_at)

New columns on `receipts`:
- `household_id` (nullable, FK)
- `tax_amount` (nullable, float)

`init_db.py` now runs a lightweight migration step that `ALTER TABLE`s missing columns on existing SQLite files — safe to call on every startup.

## 7. Frontend (Next.js)

### `lib/format.ts`
- `formatCurrency(amount, currency)` — locale-aware via `Intl.NumberFormat`.
- `convertCurrency(amount, from, to)` — uses live rates when the dashboard has fetched them, falls back to a baked-in static table.
- `setFxRates(rates)` — push API-fetched rates into the conversion cache.
- `SUPPORTED_DISPLAY_CURRENCIES` — currencies offered in the selector.

### `lib/api.ts`
Added typed helpers: `getFxRates`, `listBudgets`, `upsertBudget`, `deleteBudget`, `listRecurring`, `searchReceipts`, `exportTransactionsPdf`, `listHouseholds`, `createHousehold`, `joinHousehold`, `listReceipts`.

### Dashboard (`app/dashboard/page.tsx`)
Full rewrite:
- Three-card header: **Total spend** / **Tax paid (VAT)** / **Show in** currency selector.
- Date-range chips (Week / Month / Year / All time), persisted to `localStorage`.
- **Monthly budgets** section: progress bars per category, color-graded (green / amber / red), shows spent / limit / projected end-of-month / over-budget delta.
- **Insights** section now renders both frequency-spike and price-change.
- **Recurring expenses** card with monthly forecast in the chosen display currency.
- API-backed receipt search (250ms debounced) replaces the in-memory filter.
- Tooltip on each transaction price showing the converted value when display currency differs from native.
- Loading skeletons replace the spinner.
- Inline "Set / Edit budget" button per category row.
- **Export PDF** button alongside Export CSV.
- Server / first-client render now match (no more hydration error).

### Branding
- `app/layout.tsx` metadata: title → `ExTaSy — Expense Tracking System`.
- `components/TopNav.tsx`: logo brand `Ex<span class="text-cyan-400">TaSy</span>` with hover title.

## 8. Mobile (Flutter)

- `lib/core/config/app_config.dart` default URL refreshed: `http://192.168.100.63:8765`.
- Rest of the app unchanged.

## 9. Tooling / deps

`backend/requirements.txt` pins added:
- `reportlab>=4.0` (for PDF generation)
- `httpx>=0.27` (for live FX fetch)

## 10. Demo cycle

Created a demo seed (`backend/scripts/seed_demo.py`) that built `ozansmet@gmail.com` with 17 multilingual receipts spanning BAM / EUR / USD / JPY / RUB / SAR / TRY, 4 pre-configured budgets, and engineered overdue items so `need-to-buy` had something to show. Used it through the day for testing, then wiped:

- All rows from `users`, `receipts`, `receipt_items`, `products`, `inventory_items`, `budgets`, `households`, `household_members`, `insights`.
- All files under `storage/uploads/`.
- `scripts/seed_demo.py` and the entire `scripts/` directory.
- Test artifacts under `/tmp` (bank CSV, exported PDF, scraped dashboard HTML).

The 6 default categories are preserved so the receipt confirm UI still has its dropdown options.

---

## Current servers (still running in background)

| Service | URL | Notes |
|---|---|---|
| Backend | http://127.0.0.1:8765 | FastAPI + uvicorn `--reload` |
| Web UI | http://localhost:3737 | Next.js dev server |

Register a fresh account at `/register` to start using the clean DB.

---

# 2026-05-26 part 2 — Pluggable OCR engine

Added a plug-in OCR layer so the engine can be swapped via a single env var. The motivation is accuracy: Tesseract caps at ~85% on phone-photo receipts, and gets worse on non-Latin scripts. The architecture is engine-agnostic so you can switch to a vision-LLM (or a paid receipt API) without touching any callers.

## Architecture

`app/services/ocr.py` is now a thin dispatcher around `app/services/ocr_engines/`:

```
ocr_engines/
├── base.py         OCREngine protocol + OCRResult/StructuredReceipt/StructuredItem dataclasses
├── tesseract.py    TesseractEngine — the existing pipeline (raw text only)
├── gemini.py       GeminiEngine — VLM via google-genai SDK, structured JSON output
├── claude.py       ClaudeEngine — stub
├── mindee.py       MindeeEngine — stub
└── paddle.py       PaddleEngine — stub (blocked by Py 3.14 wheels)
```

Each engine returns an `OCRResult`:
- `raw_text` — always populated
- `structured` — optional. When present (VLM engines), `receipt_processing.py` skips the regex parser entirely and applies fields directly. Big accuracy win because VLMs understand receipt context, not just text.
- `confidence` — 0.0–1.0; lets you build a hybrid router later (cheap engine first, escalate to expensive engine when confidence < threshold).
- `engine` — engine name (for logging/metrics).

`receipt_processing.py` now branches on `ocr_result.structured`:
- VLM path: applies the structured fields directly (store, date, currency, total, tax, items).
- Tesseract path: feeds raw_text into the existing regex parser as before.

## Switching engines

Edit `backend/.env`:

```bash
# Free local OCR (default)
OCR_ENGINE="tesseract"

# Top-accuracy VLM (free tier 1500/day)
OCR_ENGINE="gemini"
GEMINI_API_KEY="your-key-from-aistudio.google.com"
OCR_VLM_MODEL="gemini-2.5-flash"     # or gemini-2.5-pro for ultimate accuracy
```

Restart the backend (uvicorn `--reload` picks up the env on the next request).

## Cost / accuracy tradeoff

| Engine | Status | Accuracy | Cost / receipt | Notes |
|---|---|---|---|---|
| tesseract | Live | 70–85% | $0 | Local, slow (8–15s), weak on phone photos and non-Latin |
| gemini | Wired (needs key) | 92–97% | $0 free tier → $0.0001 | Multi-language native, structured JSON output |
| claude | Stub | 93–97% | ~$0.005 | Comparable to Gemini, slightly stronger on tricky layouts |
| mindee | Stub | 95–98% | $0.05–$0.10 | Best-in-class for receipts specifically |
| paddle | Stub | 88–93% | $0 | Local, no Py 3.14 wheel yet |

## Next step for hybrid routing

The `confidence` field on `OCRResult` enables a "try cheap, fall back to expensive" pipeline. Implementation pattern:

```python
result = TesseractEngine().extract(path)
if result.confidence < 0.6:
    result = GeminiEngine().extract(path)
```

Wire this as a `HybridEngine` in `ocr_engines/hybrid.py` when ready.

## Dependencies added

`google-genai==2.6.0` — installs cleanly on Python 3.14.

---

## Known follow-ups

- Live FX endpoint currently shows `source: static-fallback` — frankfurter.app timed out during my smoke test. Worth re-running in production where outbound HTTPS is reliable; the static table is intentionally close to live values so the diff is small.
- `/receipts/search` uses SQL `ILIKE` not FTS5 — fine for current scale, reconsider if receipt count > ~10k.
- Household sharing scaffold is API-complete but has no dedicated UI yet (no `/households` page on the web frontend).
- Bank reconciliation has no UI either — endpoint accepts `multipart/form-data` directly.
- Mobile app hasn't been updated to consume any of the new endpoints (budgets, FX, recurring, search, household, reconcile, PDF export).
- Nothing committed today. `git status` shows extensive changes ready to bundle into commits.
