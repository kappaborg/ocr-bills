"""Auth round-trip: register → login → /auth/me."""
from __future__ import annotations


def test_register_login_me_round_trip(client):
    r = client.post("/auth/register", json={"email": "alice@example.com", "password": "testpass123"})
    assert r.status_code in (200, 201), r.text
    token = r.json()["access_token"]
    assert token

    r = client.post("/auth/login", json={"email": "alice@example.com", "password": "testpass123"})
    assert r.status_code == 200
    assert r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


def test_login_with_wrong_password(client):
    client.post("/auth/register", json={"email": "bob@example.com", "password": "testpass123"})
    r = client.post("/auth/login", json={"email": "bob@example.com", "password": "wrong-password"})
    assert r.status_code == 400


def test_me_without_token_is_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_register_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": "carol@example.com", "password": "short"})
    assert r.status_code == 400


def test_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "dave@example.com", "password": "testpass123"})
    r = client.post("/auth/register", json={"email": "dave@example.com", "password": "testpass123"})
    assert r.status_code == 400
