from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _normalize_url(url: str) -> str:
    """
    Force the psycopg3 driver for Postgres URLs. Various PaaS providers emit
    `postgres://`, `postgresql://`, or `postgresql+psycopg2://` — SQLAlchemy 2.x
    defaults the bare schemes to psycopg2, which has no Py 3.14 wheels. Coerce
    them all to `postgresql+psycopg://` so we always use psycopg 3.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url[len("postgresql+psycopg2://"):]
    return url


_url = _normalize_url(settings.DATABASE_URL)
_is_sqlite = _url.startswith("sqlite")

engine = create_engine(
    _url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Sensible pool defaults for a small-to-medium production load. SQLite
    # ignores these (it doesn't pool); Postgres uses them.
    pool_pre_ping=not _is_sqlite,
    pool_recycle=1800 if not _is_sqlite else -1,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

