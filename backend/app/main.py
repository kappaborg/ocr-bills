from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import router
from app.db.session import SessionLocal
from app.db.init_db import init_db, ensure_upload_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
