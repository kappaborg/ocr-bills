from fastapi import APIRouter

from app.api.routes import (
    auth,
    budgets,
    fx,
    households,
    insights,
    inventory,
    meta,
    receipts,
    recommendations,
    reconcile,
    transactions,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
router.include_router(insights.router, prefix="/insights", tags=["insights"])
router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
router.include_router(meta.router, prefix="/meta", tags=["meta"])
router.include_router(fx.router, prefix="/fx", tags=["fx"])
router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
router.include_router(households.router, prefix="/households", tags=["households"])
router.include_router(reconcile.router, prefix="/reconcile", tags=["reconcile"])

