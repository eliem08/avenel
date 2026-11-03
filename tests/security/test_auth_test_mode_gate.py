"""Regression tests for the subject-header auth bypass (Phase 5c-1, apps/api/deps.py).

Before 5c-1 any caller could authenticate as any user by sending `X-Identity-Subject`
or a non-JWT bearer token, and could claim fresh MFA with `X-Auth-Time` /
`X-MFA-Authenticated`. Those paths now exist only when AVENEL_AUTH_TEST_MODE=1.
"""

from __future__ import annotations

import time
import uuid

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.tenancy.jwt import get_jwt_verifier
from tests.helpers import seed_membership, seed_tenant, seed_user


@pytest.fixture
def accountant(db_conn: psycopg.Connection) -> dict:
    t_id = seed_tenant(db_conn, "Cabinet Gate Test")
    sub = f"gate-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="accountant")
    db_conn.commit()
    return {"tenant_id": t_id, "sub": sub, "user_id": u_id}


@pytest.fixture
def production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AVENEL_AUTH_TEST_MODE", raising=False)


def test_subject_header_rejected_outside_test_mode(accountant, production_mode):
    client = TestClient(app)
    r = client.get("/v1/me", headers={"X-Identity-Subject": accountant["sub"]})
    assert r.status_code == 401


def test_plain_bearer_rejected_outside_test_mode(accountant, production_mode):
    client = TestClient(app)
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {accountant['sub']}"})
    assert r.status_code == 401


def test_forged_mfa_headers_rejected_outside_test_mode(accountant, production_mode):
    client = TestClient(app)
    r = client.post(
        f"/v1/approvals/{uuid.uuid4()}:decide",
        headers={
            "X-Identity-Subject": accountant["sub"],
            "Idempotency-Key": str(uuid.uuid4()),
            "X-Auth-Time": str(int(time.time())),
            "X-MFA-Authenticated": "true",
        },
        json={"decision": "approved", "reason": "test", "subject_hash": "0" * 64},
    )
    assert r.status_code == 401


def test_subject_header_still_works_in_test_mode(accountant):
    """The suite itself relies on this path; it must remain available under the flag."""
    client = TestClient(app)
    r = client.get("/v1/me", headers={"X-Identity-Subject": accountant["sub"]})
    assert r.status_code == 200, r.text


def test_jwt_with_stale_auth_time_cannot_decide_even_with_forged_header(accountant, production_mode):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update({"kid": "gate-key", "alg": "RS256", "use": "sig"})
    get_jwt_verifier().set_jwks({"keys": [jwk]})
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": accountant["sub"], "iss": "http://localhost:8080/realms/avenel", "aud": "avenel-api",
            "iat": now, "exp": now + 600, "nbf": now, "amr": ["pwd", "otp"], "auth_time": now - 3600,
        },
        key, algorithm="RS256", headers={"kid": "gate-key"},
    )
    client = TestClient(app)
    r = client.post(
        f"/v1/approvals/{uuid.uuid4()}:decide",
        headers={
            "Authorization": f"Bearer {token}", "X-Auth-Time": str(now),
            "X-MFA-Authenticated": "true", "Idempotency-Key": str(uuid.uuid4()),
        },
        json={"decision": "approved", "reason": "test", "subject_hash": "0" * 64},
    )
    assert r.status_code == 401
    assert "insufficient_user_authentication" in r.headers.get("www-authenticate", "")
