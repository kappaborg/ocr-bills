"""Billing endpoints + plan gating."""
from __future__ import annotations


def test_plans_endpoint_returns_three_tiers(client):
    r = client.get("/billing/plans")
    assert r.status_code == 200
    plans = r.json()["plans"]
    ids = [p["id"] for p in plans]
    assert ids == ["free", "pro", "business"]
    assert all(isinstance(p["features"], list) and p["features"] for p in plans)


def test_billing_me_defaults_to_free(client, auth_headers):
    r = client.get("/billing/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "free"
    assert data["usage"]["receipts_used"] == 0
    assert data["usage"]["receipts_quota"] == 20


def test_pdf_export_blocked_for_free_user(client, auth_headers):
    r = client.get("/transactions/export.pdf", headers=auth_headers)
    assert r.status_code == 402
    assert r.headers.get("X-Upgrade-Required") == "pro"


def test_budgets_blocked_for_free_user(client, auth_headers):
    r = client.get("/budgets", headers=auth_headers)
    assert r.status_code == 402


def test_households_blocked_for_free_user(client, auth_headers):
    r = client.get("/households", headers=auth_headers)
    assert r.status_code == 402
    assert r.headers.get("X-Upgrade-Required") == "business"


def test_reconcile_blocked_for_free_user(client, auth_headers):
    r = client.get("/reconcile/sample.csv", headers=auth_headers)
    assert r.status_code == 402


def test_generic_csv_export_works_for_free_user(client, auth_headers):
    r = client.get("/transactions/export.csv?format=generic", headers=auth_headers)
    assert r.status_code == 200
    assert "date,merchant,item" in r.text.splitlines()[0]


def test_quickbooks_csv_blocked_for_free_user(client, auth_headers):
    r = client.get("/transactions/export.csv?format=quickbooks", headers=auth_headers)
    assert r.status_code == 402


def test_xero_csv_blocked_for_free_user(client, auth_headers):
    r = client.get("/transactions/export.csv?format=xero", headers=auth_headers)
    assert r.status_code == 402


def test_unknown_export_format_400s(client, auth_headers):
    r = client.get("/transactions/export.csv?format=banana", headers=auth_headers)
    assert r.status_code == 400


def test_checkout_503_when_stripe_unconfigured(client, auth_headers):
    r = client.post("/billing/checkout", headers=auth_headers, json={"plan": "pro"})
    assert r.status_code == 503
    assert "STRIPE_SECRET_KEY" in r.json()["detail"]
