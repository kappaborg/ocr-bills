import enum
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    """Return a naive UTC datetime (timezone-info-free) without using deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
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
    budgets = relationship("Budget", back_populates="user")
    household_memberships = relationship("HouseholdMember", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")


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

    # Optional household scope — when set, receipt is visible to all household members.
    household_id: Mapped[int] = mapped_column(Integer, ForeignKey("households.id"), nullable=True, index=True)

    # Parsed PDV/VAT amount in the receipt's currency (None when undetected).
    tax_amount: Mapped[float] = mapped_column(Float, nullable=True)

    # 200x200 JPEG thumbnail (~10-20 KB) persisted in the DB. The original
    # image lives in ephemeral UPLOAD_DIR on HF Spaces and dies on every
    # restart — the thumbnail surviving in Postgres keeps list views visual.
    thumbnail: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="receipts")
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")
    household = relationship("Household", back_populates="receipts")


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


class PriceObservation(Base):
    """
    Anonymous crowdsourced price point harvested from confirmed receipts.

    Deliberately carries NO user_id — observations are anonymous by
    construction so the cross-user price feed can never leak who shops
    where. receipt_item_id is internal lineage for dedup/moderation only
    and must never be exposed through the API.
    """

    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_normalized: Mapped[str] = mapped_column(String(255), index=True)
    store_normalized: Mapped[str] = mapped_column(String(255), index=True)
    store_display: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    unit_price: Mapped[float] = mapped_column(Float, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    region: Mapped[str] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="receipt")
    receipt_item_id: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class StoreLink(Base):
    """
    Curated landing destinations per normalized store. Platform URLs are
    hand-verified before insertion — a broken Glovo deep link is worse than
    the always-working maps fallback the resolver uses when these are NULL.
    """

    __tablename__ = "store_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_normalized: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    city: Mapped[str] = mapped_column(String(64), nullable=True)
    glovo_url: Mapped[str] = mapped_column(String(512), nullable=True)
    wolt_url: Mapped[str] = mapped_column(String(512), nullable=True)
    shop_url: Mapped[str] = mapped_column(String(512), nullable=True)
    maps_query: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ClientEvent(Base):
    """Lightweight product-analytics events (e.g. price-chip taps). The
    tap-through data is the evidence base for future retailer partnerships."""

    __tablename__ = "client_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    store: Mapped[str] = mapped_column(String(255), nullable=True)
    product: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class ShoppingListItem(Base):
    """
    One entry on the user's single active shopping list. No separate lists
    table in v1 — "the list" is implicit per user. Checked items stay until
    explicitly cleared so the user can review what they bought.
    """

    __tablename__ = "shopping_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    product_normalized: Mapped[str] = mapped_column(String(255), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(32), default="manual")  # manual | need_to_buy
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class Budget(Base):
    """Monthly spending limit per category for a single user, in any currency."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)

    monthly_limit: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="BAM")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="budgets")
    category = relationship("Category")


class Household(Base):
    """A group of users who share receipts (e.g. a family or couple)."""

    __tablename__ = "households"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    # Random share-link token; anyone with this token can join.
    invite_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    members = relationship("HouseholdMember", back_populates="household", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="household")


class HouseholdMember(Base):
    __tablename__ = "household_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    household_id: Mapped[int] = mapped_column(Integer, ForeignKey("households.id"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")  # 'owner' | 'member'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    household = relationship("Household", back_populates="members")
    user = relationship("User", back_populates="household_memberships")


class ProcessedStripeEvent(Base):
    """
    Dedup table for Stripe webhook delivery. Stripe retries events on 5xx and
    timeout; without this table a retried `customer.subscription.updated`
    would re-sync the subscription (mostly idempotent but wasteful) and a
    retried `checkout.session.completed` would issue a second Stripe API call.
    """
    __tablename__ = "processed_stripe_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Plan(str, enum.Enum):
    free = "free"
    pro = "pro"
    business = "business"


class SubscriptionStatus(str, enum.Enum):
    active = "active"           # paid, in good standing
    trialing = "trialing"       # in trial period
    past_due = "past_due"       # Stripe failed to charge, grace period
    canceled = "canceled"       # ended; user reverts to free
    incomplete = "incomplete"   # checkout abandoned mid-flow


class Subscription(Base):
    """One row per user, tracking their active billing plan."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)

    plan: Mapped[str] = mapped_column(String(16), default=Plan.free.value)
    status: Mapped[str] = mapped_column(String(24), default=SubscriptionStatus.active.value)

    # Stripe references — null for the implicit free tier
    stripe_customer_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)

    # End of the current paid period — used to compute the quota window
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="subscription")


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

