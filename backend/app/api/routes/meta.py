from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.init_db import init_db
from app.db.models import Category, InventoryItem, Product, Receipt, ReceiptStatus
from app.services.product_normalization import normalize_product_name


router = APIRouter()


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """Global category list — used by the frontend item editor. No auth required."""
    init_db(db)
    cats = db.query(Category).filter(Category.user_id.is_(None)).order_by(Category.id).all()
    return [{"id": c.id, "name": c.name} for c in cats]


@router.get("/ocr")
def ocr_meta():
    """Returns OCR capabilities useful for debugging deployments."""
    try:
        import pytesseract
        langs = pytesseract.get_languages(config="")
    except Exception:
        langs = []

    return {
        "tesseract_langs_env": settings.TESSERACT_LANGS,
        "installed_langs": langs,
    }


@router.post("/reindex-inventory")
def reindex_inventory(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Rebuild the products and inventory_items tables for the current user
    from all their confirmed receipts.

    Safe to call multiple times — it upserts rather than deletes.
    Useful when confirmed receipts pre-date the inventory-tracking feature.
    """
    init_db(db)

    confirmed = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id, Receipt.processing_status == ReceiptStatus.confirmed.value)
        .all()
    )

    # Reset existing inventory counts so rebuild is idempotent (safe to call multiple times).
    existing_inv = db.query(InventoryItem).filter(InventoryItem.user_id == user.id).all()
    for inv in existing_inv:
        inv.purchase_count = 0
        inv.avg_interval_days = None
        inv.last_purchased_at = None
    db.flush()

    upserted_products = 0
    upserted_inventory = 0

    for receipt in confirmed:
        purchased_at = receipt.receipt_date or receipt.created_at or datetime.now(timezone.utc).replace(tzinfo=None)

        for item in receipt.items:
            norm = normalize_product_name(item.item_name)
            if not norm:
                continue

            product = (
                db.query(Product)
                .filter(Product.user_id == user.id, Product.name_normalized == norm)
                .first()
            )

            if product is None:
                # Fuzzy match for near-duplicates.
                try:
                    from difflib import SequenceMatcher
                    candidates = (
                        db.query(Product)
                        .filter(Product.user_id == user.id)
                        .order_by(Product.id.desc())
                        .limit(400)
                        .all()
                    )
                    best, best_ratio = None, 0.0
                    for c in candidates:
                        r = SequenceMatcher(None, norm, c.name_normalized).ratio()
                        if r > best_ratio:
                            best_ratio, best = r, c
                    if best is not None and best_ratio >= 0.90:
                        product = best
                except Exception:
                    pass

            if product is None:
                product = Product(
                    user_id=user.id,
                    name=item.item_name[:255],
                    name_normalized=norm[:255],
                    category_id=item.category_id,
                )
                db.add(product)
                db.flush()
                upserted_products += 1
            elif product.category_id is None and item.category_id is not None:
                product.category_id = item.category_id

            inv = db.query(InventoryItem).filter(InventoryItem.product_id == product.id).first()
            if inv is None:
                inv = InventoryItem(
                    user_id=user.id,
                    product_id=product.id,
                    last_purchased_at=purchased_at,
                    purchase_count=1,
                    avg_interval_days=None,
                )
                db.add(inv)
                upserted_inventory += 1
            else:
                prev_last = inv.last_purchased_at
                prev_count = inv.purchase_count or 0
                if prev_last is not None and purchased_at > prev_last:
                    interval_days = (purchased_at - prev_last).total_seconds() / 86400.0
                    if interval_days > 0.01:
                        prev_intervals = max(prev_count - 1, 1)
                        if inv.avg_interval_days is None:
                            inv.avg_interval_days = interval_days
                        else:
                            inv.avg_interval_days = (
                                inv.avg_interval_days * prev_intervals + interval_days
                            ) / (prev_intervals + 1)
                if prev_last is None or purchased_at > prev_last:
                    inv.last_purchased_at = purchased_at
                inv.purchase_count = prev_count + 1
                inv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                upserted_inventory += 1

            db.add(product)
            db.add(inv)

    db.commit()

    return {
        "receipts_processed": len(confirmed),
        "products_upserted": upserted_products,
        "inventory_rows_upserted": upserted_inventory,
    }
