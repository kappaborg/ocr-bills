from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import router
from app.db.session import SessionLocal
from app.db.init_db import init_db, ensure_upload_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to serve with the repo-visible default JWT secret outside local
    # dev — anyone reading the public GitHub repo could forge session tokens
    # for any user. This bit us in production on 2026-06-12: the HF Space ran
    # for weeks without JWT_SECRET set. Set it via env/HF Space secret:
    #   openssl rand -hex 32
    if settings.JWT_SECRET == "change-me" and settings.ENVIRONMENT != "local":
        raise RuntimeError(
            "JWT_SECRET is still the default 'change-me' — refusing to start "
            "outside local dev. Set the JWT_SECRET env var (openssl rand -hex 32)."
        )
    if settings.JWT_SECRET == "change-me":
        import logging
        logging.getLogger("uvicorn.error").warning(
            "JWT_SECRET is the insecure default — fine for local dev, "
            "never deploy like this."
        )

    ensure_upload_dir(settings.UPLOAD_DIR)
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.APP_NAME, version="v1", lifespan=lifespan)

_cors_origins = [
    o.strip()
    for o in getattr(settings, "FRONTEND_ORIGINS", "").split(",")
    if o.strip()
]
if not _cors_origins:
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

_cors_regex = (getattr(settings, "FRONTEND_ORIGIN_REGEX", "") or "").strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
