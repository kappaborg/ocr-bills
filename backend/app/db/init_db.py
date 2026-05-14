import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Base, Category
from app.db.session import engine


DEFAULT_CATEGORIES = ["Groceries", "Transportation", "Utilities", "Entertainment", "Healthcare", "Uncategorized"]


def init_db(db: Session) -> None:
    # Create tables if they don't exist (local dev MVP).
    Base.metadata.create_all(bind=engine)
    seed_global_categories_if_missing(db)


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

