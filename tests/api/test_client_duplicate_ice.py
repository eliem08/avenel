"""A second client with the same ICE (or a second one without ICE) is refused with 409, not a 500.

Migration 001 holds UNIQUE NULLS NOT DISTINCT (tenant_id, ice): one client per ICE per firm, and
at most one client without ICE. Found on the docker stack, where the second request crashed (500).
"""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.helpers import seed_membership, seed_tenant, seed_user


def _client(db_conn: psycopg.Connection) -> tuple[TestClient, dict[str, str]]:
    t_id = seed_tenant(db_conn, f"Cabinet ICE {uuid.uuid4()}")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")
    return TestClient(app), {"X-Identity-Subject": sub, "X-Tenant-Id": str(t_id)}


def _post(c: TestClient, h: dict[str, str], body: dict[str, str]):
    return c.post("/v1/client-entities", headers={**h, "Idempotency-Key": str(uuid.uuid4())}, json=body)


def test_same_ice_twice_is_a_409(db_conn: psycopg.Connection):
    c, h = _client(db_conn)
    assert _post(c, h, {"legal_name": "Alpha SARL", "ice": "001500000009991"}).status_code == 201
    res = _post(c, h, {"legal_name": "Beta SARL", "ice": "001500000009991"})
    assert res.status_code == 409, res.text
    assert "ICE" in res.json()["detail"]


def test_second_client_without_ice_is_a_409(db_conn: psycopg.Connection):
    c, h = _client(db_conn)
    assert _post(c, h, {"legal_name": "Sans ICE Un"}).status_code == 201
    res = _post(c, h, {"legal_name": "Sans ICE Deux"})
    assert res.status_code == 409, res.text
