---
title: ExTaSy Backend
emoji: 📊
colorFrom: cyan
colorTo: green
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Receipt OCR + expense tracking backend (FastAPI + Gemini)
---

<!--
  ↑ The YAML frontmatter above is Hugging Face Spaces metadata. HF reads it
  to know how to build the Space (Docker SDK, expose port 8000, etc.).
  Don't remove it — the rest of this file is human-readable docs.
-->

# ExTaSy — Receipt OCR + Expense Tracking Backend

FastAPI backend serving the [ExTaSy](https://github.com/kappaborg/ocr-bills) web + mobile apps.
Multi-language receipt OCR via plug-in engines (Tesseract, Gemini Flash, Claude, Mindee),
JWT auth, Stripe billing, Postgres persistence, server-sent receipt status, smart
confirm with confidence bucketing, multi-currency with live FX, household sharing,
bank reconciliation, accountant-shaped CSV / PDF exports.

## Deploy targets

This image is built and runs on three environments:

| Where | How |
|---|---|
| Local dev | `cd backend && uvicorn app.main:app --reload --port 8765` |
| Hugging Face Spaces (free, no CC) | Push this directory to a Docker Space — the frontmatter above wires it up |
| Fly.io (paid) | `fly deploy` with the included `fly.toml` |

## Required env vars (set as HF Space Secrets in production)

| Name | Example | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://...pooler.supabase.com:5432/postgres` | Postgres (Supabase free tier works) |
| `JWT_SECRET` | random 32-byte hex | `openssl rand -hex 32` |
| `GEMINI_API_KEY` | `AIza...` | Optional; high-accuracy OCR via Gemini 2.5 Flash |
| `OCR_ENGINE` | `gemini` or `tesseract` | Which engine to use |
| `FRONTEND_URL` | `https://your-app.vercel.app` | For Stripe redirects |
| `FRONTEND_ORIGINS` | comma-separated | CORS allow-list |
| `FRONTEND_ORIGIN_REGEX` | `^https://.*\.vercel\.app$` | Accepts any Vercel preview deploy |
| `STRIPE_SECRET_KEY` | `sk_test_...` | Optional; billing endpoints 503 without it |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | Optional; needed for Stripe webhooks |
| `STRIPE_PRICE_PRO` | `price_...` | Pro plan price ID |
| `STRIPE_PRICE_BUSINESS` | `price_...` | Business plan price ID |

## Local quickstart

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit DATABASE_URL etc.
uvicorn app.main:app --reload --port 8765
```

API base: `http://localhost:8765` · health check: `GET /health`.

## Architecture notes

- **OCR**: pluggable engine layer in `app/services/ocr_engines/`. Default is Tesseract; switch via `OCR_ENGINE` env var.
- **Per-user context**: Gemini gets a "Hints from this user's recent receipts" block built from their history so multi-currency and multi-language receipts disambiguate correctly.
- **Background processing**: receipt OCR runs as a FastAPI BackgroundTask; the frontend subscribes via Server-Sent Events at `GET /receipts/{id}/events`.
- **Webhook idempotency**: `processed_stripe_events` table dedupes by `event.id` so retries are safe.
- **Storage**: receipt images go to `UPLOAD_DIR` (defaults to ephemeral `/tmp` on HF Spaces — OCR'd data persists in Postgres; original photos are lost on restart, acceptable for v1).
