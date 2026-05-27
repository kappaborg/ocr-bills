"""Stripe webhook idempotency — retries must be a no-op."""
from __future__ import annotations

import json


def test_webhook_503_when_stripe_unconfigured(client):
    """With no STRIPE_SECRET_KEY the webhook endpoint refuses."""
    r = client.post("/billing/webhook", content=b"{}")
    assert r.status_code == 503


def test_webhook_idempotent_under_dev_mode(client, monkeypatch):
    """
    With STRIPE_WEBHOOK_SECRET unset, the handler accepts unsigned bodies (dev
    mode). Replaying the same event ID must not double-apply state.
    """
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dev_only")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "")

    # Reload the billing route module so it picks up the new env values.
    import importlib
    import app.core.config
    import app.api.routes.billing
    importlib.reload(app.core.config)
    importlib.reload(app.api.routes.billing)

    # Synthesize a customer.subscription.updated event. With Stripe disabled
    # the handler can't look up customer/sub from the real API, but the
    # idempotency check happens BEFORE any Stripe call — so a duplicate event
    # ID should short-circuit even when the inner sync would fail.
    event = {
        "id": "evt_test_dedup_123",
        "type": "customer.subscription.deleted",  # delete path doesn't call Stripe API
        "data": {"object": {"id": "sub_test_dedup", "customer": "cus_test"}},
    }

    r1 = client.post("/billing/webhook", content=json.dumps(event).encode())
    r2 = client.post("/billing/webhook", content=json.dumps(event).encode())

    # Both should be 2xx. Idempotency means the second is a no-op (returns the
    # "already processed" marker). The exact body shape can vary; the key
    # invariant is no 5xx and no double-apply (no double-applied state to check
    # in this synthetic event since the underlying sub doesn't exist).
    assert r1.status_code < 400, r1.text
    assert r2.status_code < 400, r2.text
    assert r2.json().get("already_processed") is True
