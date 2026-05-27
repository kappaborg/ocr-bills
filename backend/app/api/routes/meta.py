from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import InventoryItem, Receipt, ReceiptStatus
from app.services.inventory_update import update_inventory_for_receipt


router = APIRouter()


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """Global category list — used by the frontend item editor. No auth required."""
    from app.db.models import Category
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
    Rebuild products and inventory_items from all confirmed receipts.
    Safe to call multiple times — upserts rather than deletes.
    """

    # Reset existing inventory counts so rebuild is idempotent.
    existing_inv = db.query(InventoryItem).filter(InventoryItem.user_id == user.id).all()
    for inv in existing_inv:
        inv.purchase_count = 0
        inv.avg_interval_days = None
        inv.last_purchased_at = None
    db.flush()

    confirmed = (
        db.query(Receipt)
        .filter(Receipt.user_id == user.id, Receipt.processing_status == ReceiptStatus.confirmed.value)
        .all()
    )

    for receipt in confirmed:
        update_inventory_for_receipt(receipt, db)

    return {"receipts_processed": len(confirmed)}
