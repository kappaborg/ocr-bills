from fastapi import APIRouter

from app.api.routes import auth, receipts, transactions, insights, inventory, recommendations, meta

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
router.include_router(insights.router, prefix="/insights", tags=["insights"])
router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
router.include_router(meta.router, prefix="/meta", tags=["meta"])

