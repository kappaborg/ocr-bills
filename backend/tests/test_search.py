"""Multi-token receipt search."""
from __future__ import annotations


def _insert_receipt(user_id, **kw):
    from app.db.models import Receipt, ReceiptStatus
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        r = Receipt(
            user_id=user_id,
            storage_key=f"t/{user_id}/r.jpg",
            processing_status=ReceiptStatus.confirmed.value,
            **kw,
        )
        db.add(r)
        db.commit()
    finally:
        db.close()


def test_search_finds_by_store_name(client, auth_headers):
    from app.api.deps import decode_access_token
    user_id = decode_access_token(auth_headers["Authorization"].removeprefix("Bearer "))
    _insert_receipt(user_id, store_name="Konzum", raw_text="hljeb 1.50\nmlijeko 2.20")
    _insert_receipt(user_id, store_name="Bingo", raw_text="pile 12.50")

    r = client.get("/receipts/search?q=Konzum", headers=auth_headers)
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 1
    assert results[0]["store_name"] == "Konzum"


def test_search_matches_raw_text(client, auth_headers):
    from app.api.deps import decode_access_token
    user_id = decode_access_token(auth_headers["Authorization"].removeprefix("Bearer "))
    _insert_receipt(user_id, store_name="Lawson", raw_text="おにぎり 150\n緑茶 130")

    r = client.get("/receipts/search?q=おにぎり", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1


def test_search_empty_query_returns_empty(client, auth_headers):
    r = client.get("/receipts/search?q=%20", headers=auth_headers)
    # Empty after .split() — backend returns []
    assert r.status_code == 200
    assert r.json()["results"] == []
