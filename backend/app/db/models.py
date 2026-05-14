import enum
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    """Return a naive UTC datetime (timezone-info-free) without using deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass
    __allow_unmapped__ = True


class CategoryDefault(enum.Enum):
    GLOBAL = "global"
    USER = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    receipts = relationship("Receipt", back_populates="user")
    categories = relationship("Category", back_populates="user")
    insights = relationship("Insight", back_populates="user")
    products = relationship("Product", back_populates="user")
    inventory_items = relationship("InventoryItem", back_populates="user")


class ReceiptStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    parsed = "parsed"
    confirmed = "confirmed"
    error = "error"


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    # Storage
    storage_key: Mapped[str] = mapped_column(String(1024))  # path-like key

    # OCR / parse output
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    detected_language: Mapped[str] = mapped_column(String(32), nullable=True)
    receipt_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    store_name: Mapped[str] = mapped_column(String(255), nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=True)

    processing_status: Mapped[str] = mapped_column(String(32), default=ReceiptStatus.queued.value)
    processing_error: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="receipts")
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(Integer, ForeignKey("receipts.id"), index=True)

    item_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[float] = mapped_column(Float, nullable=True)
    unit_price: Mapped[float] = mapped_column(Float, nullable=True)
    item_price: Mapped[float] = mapped_column(Float)

    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)

    receipt = relationship("Receipt", back_populates="items")
    category = relationship("Category", back_populates="items")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)

    user = relationship("User", back_populates="categories")
    items = relationship("ReceiptItem", back_populates="category")
    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    # Display + matching
    name: Mapped[str] = mapped_column(String(255))
    name_normalized: Mapped[str] = mapped_column(String(255), index=True)

    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="products")
    category = relationship("Category", back_populates="products")
    inventory = relationship("InventoryItem", back_populates="product", uselist=False, cascade="all, delete-orphan")


class InventoryItem(Base):
    """
    Lightweight per-user product stats used for 'what to buy' recommendations.
    Updated when receipts are confirmed.
    """

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), unique=True, index=True)

    last_purchased_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_interval_days: Mapped[float] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="inventory_items")
    product = relationship("Product", back_populates="inventory")


class InsightType(str, enum.Enum):
    frequency_spike = "frequency_spike"
    spending_spike = "spending_spike"
    price_increase = "price_increase"
    info = "info"


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    type: Mapped[str] = mapped_column(String(64), default=InsightType.info.value)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="insights")

