import os

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Base, Category
from app.db.session import engine


DEFAULT_CATEGORIES = ["Groceries", "Transportation", "Utilities", "Entertainment", "Healthcare", "Uncategorized"]


def init_db(db: Session) -> None:
    # Create tables if they don't exist (local dev MVP).
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations(db)
    _ensure_fts_index(db)
    seed_global_categories_if_missing(db)


def _column_exists(db: Session, table: str, column: str) -> bool:
    rows = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _apply_lightweight_migrations(db: Session) -> None:
    """
    Add columns to existing tables when the schema has been extended.
    SQLite's CREATE TABLE IF NOT EXISTS won't add columns to a table that
    already exists, so we ALTER explicitly. Safe to run on every startup.
    """
    if not _column_exists(db, "receipts", "household_id"):
        db.execute(text("ALTER TABLE receipts ADD COLUMN household_id INTEGER"))
    if not _column_exists(db, "receipts", "tax_amount"):
        db.execute(text("ALTER TABLE receipts ADD COLUMN tax_amount REAL"))
    db.commit()


def _ensure_fts_index(db: Session) -> None:
    """
    Drop any prior FTS5 external-content table + triggers — search is now
    implemented as a SQL LIKE scan in the search endpoint (simple, robust,
    fast enough for demo / SMB-scale data; FTS5 can be re-introduced later).
    """
    for stmt in (
        "DROP TRIGGER IF EXISTS receipts_au",
        "DROP TRIGGER IF EXISTS receipts_ad",
        "DROP TRIGGER IF EXISTS receipts_ai",
        "DROP TABLE IF EXISTS receipts_fts",
    ):
        try:
            db.execute(text(stmt))
        except Exception:
            pass
    db.commit()


def seed_global_categories_if_missing(db: Session) -> None:
    # Global categories are stored with user_id=NULL.
    for name in DEFAULT_CATEGORIES:
        existing = db.execute(
            select(Category).where(Category.user_id.is_(None), Category.name == name)
        ).scalar_one_or_none()
        if existing is None:
            db.add(Category(user_id=None, name=name))
    db.commit()


def get_category_by_name(db: Session, *, name: str) -> Category | None:
    return db.execute(select(Category).where(Category.user_id.is_(None), Category.name == name)).scalar_one_or_none()


def ensure_upload_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

