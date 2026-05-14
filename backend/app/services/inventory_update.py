from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import InventoryItem, Product, Receipt
from app.services.product_normalization import normalize_product_name


def update_inventory_for_receipt(receipt: Receipt, db: Session) -> None:
    """Update products and inventory_items tables for all items in a confirmed receipt."""
    from difflib import SequenceMatcher

    purchased_at = receipt.receipt_date or datetime.now(timezone.utc).replace(tzinfo=None)

    for it in receipt.items:
        norm = normalize_product_name(it.item_name)
        if not norm:
            continue

        product = (
            db.query(Product)
            .filter(Product.user_id == receipt.user_id, Product.name_normalized == norm)
            .first()
        )

        if product is None:
            try:
                candidates = (
                    db.query(Product)
                    .filter(Product.user_id == receipt.user_id)
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
                user_id=receipt.user_id,
                name=it.item_name[:255],
                name_normalized=norm[:255],
                category_id=it.category_id,
            )
            db.add(product)
            db.flush()
        elif product.category_id is None and it.category_id is not None:
            product.category_id = it.category_id

        inv = db.query(InventoryItem).filter(InventoryItem.product_id == product.id).first()
        if inv is None:
            inv = InventoryItem(
                user_id=receipt.user_id,
                product_id=product.id,
                last_purchased_at=purchased_at,
                purchase_count=1,
                avg_interval_days=None,
            )
            db.add(inv)
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

            inv.last_purchased_at = purchased_at
            inv.purchase_count = prev_count + 1
            inv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        db.add(product)
        db.add(inv)

    db.commit()
