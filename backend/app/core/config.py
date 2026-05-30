from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ocr-bills"
    ENVIRONMENT: str = "local"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours — tokens were expiring mid-session

    # ── OCR engine selection ───────────────────────────────────────────────
    # One of: tesseract (default, free, local) | gemini (free tier 1500/day,
    # highest accuracy) | claude (paid) | mindee (paid, receipt-specialised) |
    # paddle (free, local — currently stubbed pending Py 3.14 wheels).
    OCR_ENGINE: str = "tesseract"

    # Gemini settings — set GEMINI_API_KEY in .env to activate the gemini engine.
    # Key from https://aistudio.google.com/app/apikey (free tier).
    GEMINI_API_KEY: str = ""
    OCR_VLM_MODEL: str = "gemini-2.5-flash"

    # Tesseract language configuration.
    # Broad default covering Latin + Cyrillic (ex-YU + Russian) receipt scripts.
    # Override via TESSERACT_LANGS env var. All of these packs are available in the
    # standard Homebrew/apt tessdata; the OCR service will skip packs not installed.
    TESSERACT_LANGS: str = "eng+rus+srp+srp_latn+bos+bul+ukr"

    UPLOAD_DIR: str = "./storage/uploads"
    DATABASE_URL: str = "sqlite:///./storage/app.db"

    # Comma-separated. Browsers treat localhost vs 127.0.0.1 as different origins — allow both for dev.
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Optional regex for dynamic origins (Vercel preview deploys, branch URLs,
    # etc.). Anchored regex — e.g. r"^https://.*\.vercel\.app$".
    FRONTEND_ORIGIN_REGEX: str = ""

    # ── Billing (Stripe) ───────────────────────────────────────────────────
    # Leave empty in dev — endpoints return 503 until configured. In production:
    # 1. Create products + recurring prices in Stripe dashboard
    # 2. Set STRIPE_SECRET_KEY (sk_test_… or sk_live_…)
    # 3. Set STRIPE_WEBHOOK_SECRET (from `stripe listen` or the webhook UI)
    # 4. Paste the recurring price IDs into STRIPE_PRICE_PRO / STRIPE_PRICE_BUSINESS
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_BUSINESS: str = ""

    # Tier quotas (override per deployment if your pricing changes)
    QUOTA_FREE_RECEIPTS_PER_MONTH: int = 20
    QUOTA_PRO_RECEIPTS_PER_MONTH: int = 500
    QUOTA_BUSINESS_RECEIPTS_PER_MONTH: int = 0  # 0 = unlimited

    # Pricing display (cents). Single source of truth — frontend pulls via /billing/plans.
    PRICE_PRO_CENTS: int = 499
    PRICE_BUSINESS_CENTS: int = 1999

    # Free trial length applied to first-time Stripe checkouts (set 0 to disable).
    TRIAL_PERIOD_DAYS: int = 14

    # Frontend URL for Stripe Checkout redirects
    FRONTEND_URL: str = "http://localhost:3737"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

