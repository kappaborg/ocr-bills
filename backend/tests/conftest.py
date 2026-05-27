"""
Shared pytest fixtures.

Each test runs against a fresh temp SQLite DB and an isolated upload dir, so
tests can't pollute each other or the dev database. The FastAPI app is built
inside the fixture so that the env vars (DATABASE_URL, UPLOAD_DIR) are picked
up before any module-level state initializes.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def tmp_env(monkeypatch, tmp_path: Path) -> Path:
    """Point DATABASE_URL + UPLOAD_DIR at fresh temp locations, then reset the
    settings singleton so the app reads them. Returns the temp dir for cleanup."""
    db_file = tmp_path / "test.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("OCR_ENGINE", "tesseract")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("JWT_SECRET", "test-secret-do-not-use-in-prod")

    # Reload every module that captures settings/engine at import time so the
    # env vars take effect inside this test.
    import importlib

    import app.core.config
    import app.db.session
    import app.db.init_db
    import app.services.rate_limit
    importlib.reload(app.core.config)
    importlib.reload(app.db.session)
    importlib.reload(app.db.init_db)
    importlib.reload(app.services.rate_limit)

    # Reload routes that reference settings/engine via module-level imports
    import app.api.deps
    import app.api.routes.billing
    import app.api.routes.budgets
    import app.api.routes.fx
    import app.api.routes.households
    import app.api.routes.receipts
    import app.api.routes.recommendations
    import app.api.routes.reconcile
    import app.api.routes.transactions
    import app.api.routes.insights
    import app.api.routes.inventory
    import app.api.routes.meta
    import app.api.routes.auth
    import app.api.router
    import app.main
    for mod in (
        app.api.deps,
        app.api.routes.auth,
        app.api.routes.billing,
        app.api.routes.budgets,
        app.api.routes.fx,
        app.api.routes.households,
        app.api.routes.receipts,
        app.api.routes.recommendations,
        app.api.routes.reconcile,
        app.api.routes.transactions,
        app.api.routes.insights,
        app.api.routes.inventory,
        app.api.routes.meta,
        app.api.router,
        app.main,
    ):
        importlib.reload(mod)

    yield tmp_path

    # Reload modules back to package defaults so other test files using
    # different env vars get clean state.
    importlib.reload(app.core.config)


@pytest.fixture
def client(tmp_env):
    """Return a FastAPI TestClient bound to the freshly-initialized app. We
    enter the lifespan context so init_db runs once (mirrors prod startup)."""
    from fastapi.testclient import TestClient
    import app.main
    with TestClient(app.main.app) as c:
        yield c


def _unique_email() -> str:
    return f"u{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def user_token(client) -> str:
    """Register a fresh user and return their JWT."""
    email = _unique_email()
    r = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth_headers(user_token) -> dict:
    return {"Authorization": f"Bearer {user_token}"}
