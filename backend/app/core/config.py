from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ocr-bills"
    ENVIRONMENT: str = "local"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours — tokens were expiring mid-session

    GOOGLE_VISION_API_KEY: str = ""

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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

