from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ocr-bills"
    ENVIRONMENT: str = "local"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours — tokens were expiring mid-session

    GOOGLE_VISION_API_KEY: str = ""

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

