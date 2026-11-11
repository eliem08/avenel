"""Tests for IdempotencyMiddleware on mutating HTTP routes.

Enforces:
- Required Idempotency-Key on every mutating route (returns 400 if missing)
- Replay: same key and identical body returns cached response
- Body mismatch: same key with different body returns 422 Unprocessable Entity
- Concurrency: concurrent in-flight request returns 409 Conflict
"""

from __future__ import annotations

import hashlib
import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.middleware import get_idempotency_store
from tests.helpers import seed_membership, seed_tenant, seed_user


def test_missing_idempotency_key_returns_400(db_conn: psycopg.Connection):
    """Mutating request without Idempotency-Key returns 400 Bad Request Problem Details."""
    t_id = seed_tenant(db_conn, "Cabinet Idempotency Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    # POST without Idempotency-Key header
    res = client.post(
        "/v1/client-entities",
        headers={"X-Identity-Subject": sub, "X-Tenant-Id": str(t_id)},
        json={"legal_name": "Entreprise Sans Cle"},
    )
    assert res.status_code == 400, res.text
    problem = res.json()
    assert problem["status"] == 400
    assert "idempotency-key" in problem["detail"].lower()


def test_idempotent_replay_returns_cached_response(db_conn: psycopg.Connection):
    """Replaying request with same key and same body returns identical cached response."""
    t_id = seed_tenant(db_conn, "Cabinet Replay Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    idem_key = str(uuid.uuid4())
    headers = {
        "X-Identity-Subject": sub,
        "X-Tenant-Id": str(t_id),
        "Idempotency-Key": idem_key,
    }
    payload = {"legal_name": "Societe Replay SARL"}

    # 1. First execution
    res1 = client.post("/v1/client-entities", headers=headers, json=payload)
    assert res1.status_code == 201, res1.text
    data1 = res1.json()

    # 2. Replay with identical key and payload
    res2 = client.post("/v1/client-entities", headers=headers, json=payload)
    assert res2.status_code == 201, res2.text
    data2 = res2.json()

    assert data1["id"] == data2["id"]
    assert data1["legal_name"] == data2["legal_name"]
    assert res2.headers.get("Idempotency-Replay") == "true"


def test_same_key_different_body_returns_422(db_conn: psycopg.Connection):
    """Reusing same idempotency key with a different request payload returns 422."""
    t_id = seed_tenant(db_conn, "Cabinet Mismatch Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    idem_key = str(uuid.uuid4())
    headers = {
        "X-Identity-Subject": sub,
        "X-Tenant-Id": str(t_id),
        "Idempotency-Key": idem_key,
    }

    # 1. First request
    res1 = client.post("/v1/client-entities", headers=headers, json={"legal_name": "Nom Original"})
    assert res1.status_code == 201

    # 2. Second request with different body but same key -> 422
    res2 = client.post("/v1/client-entities", headers=headers, json={"legal_name": "Nom Modifie"})
    assert res2.status_code == 422
    problem = res2.json()
    assert "différent" in problem["detail"].lower() or "mismatch" in problem.get("title", "").lower()


def test_concurrent_in_flight_returns_409(db_conn: psycopg.Connection):
    """Concurrent request with an in-flight key returns 409 Conflict Problem Details."""
    t_id = seed_tenant(db_conn, "Cabinet In-Flight Test")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    idem_key = str(uuid.uuid4())

    # Another API process has claimed the key and is still working on it
    payload_bytes = b'{"legal_name":"Concurrent Corp"}'
    store = get_idempotency_store()
    claim = store.claim(t_id, idem_key, "POST", "/v1/client-entities", hashlib.sha256(payload_bytes).hexdigest())
    assert claim.outcome == "started"

    headers = {
        "X-Identity-Subject": sub,
        "X-Tenant-Id": str(t_id),
        "Idempotency-Key": idem_key,
        "Content-Type": "application/json",
    }

    # Attempt to send request while key is marked in_flight -> 409
    res = client.post("/v1/client-entities", headers=headers, content=payload_bytes)
    assert res.status_code == 409
    problem = res.json()
    assert "en cours" in problem["detail"].lower() or "concurrent" in problem.get("title", "").lower()


def test_non_mutating_get_does_not_require_idempotency_key(db_conn: psycopg.Connection):
    """GET requests do not require Idempotency-Key."""
    t_id = seed_tenant(db_conn, "Cabinet Non-Mutating")
    sub = f"user-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="owner")

    client = TestClient(app)
    res = client.get(
        "/v1/client-entities",
        headers={"X-Identity-Subject": sub, "X-Tenant-Id": str(t_id)},
    )
    assert res.status_code == 200


def _owner(db_conn: psycopg.Connection, name: str) -> tuple[uuid.UUID, str]:
    t_id = seed_tenant(db_conn, name)
    sub = f"user-{uuid.uuid4()}"
    seed_membership(db_conn, seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com"), t_id, role="owner")
    return t_id, sub


def test_key_is_stored_in_postgres_and_replayed_by_another_process(db_conn: psycopg.Connection):
    """The answer survives a restart and is shared by every API process: it lives in idempotency_keys."""
    t_id, sub = _owner(db_conn, "Cabinet Durable")
    key = str(uuid.uuid4())
    headers = {"X-Identity-Subject": sub, "X-Tenant-Id": str(t_id), "Idempotency-Key": key}
    payload = {"legal_name": "Societe Durable SARL"}
    first = TestClient(app).post("/v1/client-entities", headers=headers, json=payload)
    assert first.status_code == 201, first.text

    row = db_conn.execute(
        "SELECT status, response_code, method, path FROM idempotency_keys WHERE tenant_id = %s AND key = %s",
        (t_id, key),
    ).fetchone()
    assert row == ("completed", 201, "POST", "/v1/client-entities")

    # A fresh store (as in another worker process, or after a restart) sees the same answer.
    body = b'{"legal_name":"Societe Durable SARL"}'
    claim = get_idempotency_store().claim(t_id, key, "POST", "/v1/client-entities", hashlib.sha256(body).hexdigest())
    assert claim.outcome in ("replay", "mismatch")  # byte-exact body decides; never "started"
    again = TestClient(app).post("/v1/client-entities", headers=headers, json=payload)
    assert again.headers.get("Idempotency-Replay") == "true"
    assert again.json()["id"] == first.json()["id"]
    count = db_conn.execute(
        "SELECT count(*) FROM client_entities WHERE tenant_id = %s AND legal_name = %s", (t_id, payload["legal_name"])
    ).fetchone()
    assert count == (1,)


def test_same_key_from_another_tenant_never_replays_the_first_tenants_answer(db_conn: psycopg.Connection):
    """Tenant isolation: a key is only meaningful inside the tenant that used it."""
    a_id, a_sub = _owner(db_conn, "Cabinet A")
    b_id, b_sub = _owner(db_conn, "Cabinet B")
    key, payload = str(uuid.uuid4()), {"legal_name": "Meme Nom SARL"}
    client = TestClient(app)
    res_a = client.post("/v1/client-entities", json=payload,
                        headers={"X-Identity-Subject": a_sub, "X-Tenant-Id": str(a_id), "Idempotency-Key": key})
    res_b = client.post("/v1/client-entities", json=payload,
                        headers={"X-Identity-Subject": b_sub, "X-Tenant-Id": str(b_id), "Idempotency-Key": key})
    assert res_a.status_code == 201 and res_b.status_code == 201
    assert res_b.headers.get("Idempotency-Replay") is None
    assert res_b.json()["id"] != res_a.json()["id"]


def test_replay_is_refused_without_authentication(db_conn: psycopg.Connection):
    """A stored answer is never served to a caller who is not authenticated for the tenant."""
    t_id, sub = _owner(db_conn, "Cabinet Auth Replay")
    key, payload = str(uuid.uuid4()), {"legal_name": "Societe Privee SARL"}
    client = TestClient(app)
    ok = client.post("/v1/client-entities", json=payload,
                     headers={"X-Identity-Subject": sub, "X-Tenant-Id": str(t_id), "Idempotency-Key": key})
    assert ok.status_code == 201
    anonymous = client.post("/v1/client-entities", json=payload, headers={"Idempotency-Key": key})
    assert anonymous.status_code == 401
    assert "Societe Privee" not in anonymous.text


def test_claim_left_by_a_crashed_process_is_released_after_the_stale_delay(db_conn: psycopg.Connection):
    from apps.api.idempotency import STALE_IN_PROGRESS_MINUTES

    t_id, _ = _owner(db_conn, "Cabinet Stale")
    key, sha = str(uuid.uuid4()), hashlib.sha256(b"{}").hexdigest()
    store = get_idempotency_store()
    assert store.claim(t_id, key, "POST", "/v1/x", sha).outcome == "started"
    assert store.claim(t_id, key, "POST", "/v1/x", sha).outcome == "in_progress"
    db_conn.execute(
        "UPDATE idempotency_keys SET created_at = now() - make_interval(mins => %s) WHERE tenant_id = %s AND key = %s",
        (STALE_IN_PROGRESS_MINUTES + 1, t_id, key),
    )
    db_conn.commit()
    assert store.claim(t_id, key, "POST", "/v1/x", sha).outcome == "started"


def test_server_errors_are_not_kept_so_the_same_key_can_retry(db_conn: psycopg.Connection):
    from types import SimpleNamespace

    from apps.api.idempotency import finish

    t_id, _ = _owner(db_conn, "Cabinet Retry")
    key, sha = str(uuid.uuid4()), hashlib.sha256(b"{}").hexdigest()
    store = get_idempotency_store()
    assert store.claim(t_id, key, "POST", "/v1/x", sha).outcome == "started"
    request = SimpleNamespace(state=SimpleNamespace(idempotency_claim=(t_id, key)))
    finish(store, request, 503, b'{"detail":"indisponible"}')
    assert store.claim(t_id, key, "POST", "/v1/x", sha).outcome == "started"
