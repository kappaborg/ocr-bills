# ◈ ExTaSy — Expense Tracking System

Snap a photo of a receipt, get structured expenses back. ExTaSy is a full-stack receipt OCR and expense-tracking platform: a FastAPI backend, a Next.js web app, and a Flutter mobile app (iOS + Android) sharing one API.

Built for real-world receipts — multi-language (Latin, Cyrillic, Arabic, CJK, Devanagari, Thai and more), multi-currency (~40 currencies with live FX), and messy thermal-printer output.

## Features

- **Receipt OCR** — photograph or upload a receipt; a background pipeline extracts store, date, line items, and totals. Pluggable engine layer: Tesseract (default, free), Gemini 2.5 Flash, Claude, or Mindee — switch with one env var.
- **Smart confirm** — parsed items come back with confidence bucketing so users only review what the OCR was unsure about. Per-user context hints from recent receipts disambiguate currency and language.
- **Live status** — receipt processing streams to the client over Server-Sent Events.
- **Expense tracking** — transactions, budgets, category insights, and a weekly summary email.
- **Multi-currency** — ~40 currencies with locale-aware formatting and live FX conversion.
- **Household sharing** — share expenses and budgets across household members.
- **Inventory & shopping list** — purchased items feed a pantry inventory, price observations power a "Market Pulse" shopping-list builder with tap-to-buy price chips.
- **Bank reconciliation** — match receipts against bank statement lines.
- **Exports** — accountant-shaped CSV and PDF exports.
- **Billing** — Stripe Checkout with Pro / Business plans and idempotent webhooks.
- **Auth & safety** — JWT auth, rate limiting (proxy-aware, email-keyed login limits), production startup guards.

## Repository layout

```
├── backend/            FastAPI backend (Python 3.11+, SQLAlchemy 2.0, Postgres/SQLite)
│   └── frontend/       Next.js 14 web app (TypeScript + Tailwind)
├── mobile/             Flutter app — iOS & Android (Riverpod, go_router, dio)
├── DEPLOY.md           Deployment notes
└── TRAINING.md         OCR training / tuning notes
```

## Architecture

```
 Flutter app ─┐
              ├──► FastAPI backend ──► OCR engine (Tesseract / Gemini / Claude / Mindee)
 Next.js web ─┘         │
                        ├──► Postgres (Supabase) — receipts, transactions, inventory
                        ├──► Stripe — billing + webhooks
                        └──► SSE — live receipt-processing status
```

- **API routes**: auth, receipts, transactions, budgets, insights, inventory, shopping list, households, reconcile, fx, billing, events, admin, meta.
- **OCR pipeline**: EXIF rotation, adaptive preprocessing, script detection via Tesseract OSD, language-pack selection across 27 scripts, numeral-system translation (Arabic-Indic, Devanagari, Thai, …).
- **Background processing**: OCR runs as a FastAPI BackgroundTask; clients subscribe to `GET /receipts/{id}/events`.

## Quickstart

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DATABASE_URL, JWT_SECRET, etc.
uvicorn app.main:app --reload --port 8765
```

API base: `http://localhost:8765` · health check: `GET /health` · interactive docs: `/docs`.

Key env vars (full table in [`backend/README.md`](backend/README.md)):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (falls back to local SQLite) |
| `JWT_SECRET` | Required in production — `openssl rand -hex 32` |
| `OCR_ENGINE` | `tesseract` (default) or `gemini` |
| `GEMINI_API_KEY` | Optional, enables high-accuracy Gemini OCR |
| `STRIPE_SECRET_KEY` | Optional, billing endpoints return 503 without it |

### Web app

```bash
cd backend/frontend
npm install
npm run dev
```

### Mobile app

```bash
cd mobile
flutter pub get
flutter run --dart-define=API_BASE_URL=http://<your-lan-ip>:8765
```

Physical devices need your machine's LAN IP, not `localhost`. See [`mobile/SETUP.md`](mobile/SETUP.md).

### Tests

```bash
cd backend && venv/bin/pytest tests
cd mobile && flutter test
```

## Deployment

| Surface | Target |
|---|---|
| Backend | Hugging Face Spaces (Docker, free) or Fly.io (`backend/fly.toml`) |
| Web | Vercel |
| Mobile | APK sideload for Android beta; iOS via Xcode |

See [`DEPLOY.md`](DEPLOY.md) and [`backend/README.md`](backend/README.md) for environment secrets and step-by-step instructions.

## Tech stack

**Backend**: FastAPI · SQLAlchemy 2.0 · Pydantic · Postgres (psycopg 3) / SQLite · pytesseract · google-genai · Stripe · ReportLab · python-jose (JWT)

**Web**: Next.js 14 · TypeScript · Tailwind CSS

**Mobile**: Flutter · Riverpod · go_router · dio · flutter_secure_storage
