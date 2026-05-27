"""Receipt creation + free-tier quota enforcement.

These tests insert Receipt rows directly via the DB session instead of going
through /receipts/upload — that endpoint runs OCR on the uploaded image, which
needs Tesseract and a real receipt photo. The quota dependency counts rows in
the receipts table created in this period, so direct insertion is equivalent
for testing the gating logic.
"""
from __future__ import annotations


def _make_receipt(db, user_id: int, **kwargs):
    from app.db.models import Receipt, ReceiptStatus
    r = Receipt(
        user_id=user_id,
        storage_key=f"test/{user_id}/dummy.jpg",
        processing_status=kwargs.get("status", ReceiptStatus.confirmed.value),
        store_name=kwargs.get("store", "Konzum"),
        total_amount=kwargs.get("total", 10.0),
        currency=kwargs.get("currency", "BAM"),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_receipts_list_empty_for_new_user(client, auth_headers):
    r = client.get("/receipts", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_quota_dependency_blocks_after_limit(client, auth_headers):
    """Free-tier user with 20 receipts already created → 21st upload returns 402."""
    from app.api.deps import decode_access_token
    from app.db.session import SessionLocal

    # Pull user_id from token
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    user_id = decode_access_token(token)

    db = SessionLocal()
    try:
        for i in range(20):
            _make_receipt(db, user_id, store=f"Store-{i}")
    finally:
        db.close()

    # 21st should be blocked. The quota dep fires before any file reading.
    r = client.post(
        "/receipts/upload",
        headers=auth_headers,
        files={"files": ("x.jpg", b"x", "image/jpeg")},
    )
    assert r.status_code == 402, r.text
    assert "limit" in r.json()["detail"].lower()


def test_billing_me_reflects_quota_usage(client, auth_headers):
    from app.api.deps import decode_access_token
    from app.db.session import SessionLocal

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    user_id = decode_access_token(token)

    db = SessionLocal()
    try:
        for i in range(5):
            _make_receipt(db, user_id, store=f"S-{i}")
    finally:
        db.close()

    r = client.get("/billing/me", headers=auth_headers)
    assert r.status_code == 200
    usage = r.json()["usage"]
    assert usage["receipts_used"] == 5
    assert usage["receipts_quota"] == 20
    assert 24.9 <= usage["percent"] <= 25.1


def test_categories_meta_returns_defaults(client):
    r = client.get("/meta/categories")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "Groceries" in names
    assert "Transportation" in names
