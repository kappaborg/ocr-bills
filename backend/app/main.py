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


class _RealClientIPMiddleware:
    """
    Override scope["client"] with the rightmost X-Forwarded-For value (the
    one HF's proxy actually wrote), instead of trusting the leftmost — which
    is whatever the attacker chose to put in the header.

    HF Spaces' reverse proxy APPENDS to X-Forwarded-For rather than
    replacing it. With uvicorn's --proxy-headers, the leftmost value wins —
    so a client sending "X-Forwarded-For: 1.2.3.4" makes the rate limiter
    see 1.2.3.4. Rotating the spoofed IP bypasses per-IP rate limits
    entirely (verified empirically on 2026-06-13: 12 rotating-XFF
    /auth/login attempts received zero 429s).

    Pure ASGI middleware so it runs before any route or limiter touches
    request.client. Tolerates a header with N comma-separated values and
    always picks the last one — that's the IP the trusted edge proxy saw,
    independent of anything the client added.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = scope.get("headers", [])
            for name, value in headers:
                if name == b"x-forwarded-for":
                    parts = [p.strip() for p in value.decode("latin-1").split(",") if p.strip()]
                    if parts:
                        client = scope.get("client") or ("", 0)
                        scope = {**scope, "client": (parts[-1], client[1])}
                    break
        await self.app(scope, receive, send)


app.add_middleware(_RealClientIPMiddleware)

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
