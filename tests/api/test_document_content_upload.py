"""PUT /v1/documents/{id}/content (Phase 2 completion): browser uploads go through the API.

Checks: the stored bytes are exactly what was declared (size and SHA-256), originals are
write-once, scope-first 404 for other tenants and out-of-scope client users, 401 without
identity, and the full pipeline runs over HTTP only (no direct storage writes in this test).
"""

from __future__ import annotations

import datetime
import hashlib
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_client_scope, seed_membership, seed_tenant, seed_user

INVOICE = b"""
Societe Atlas Fournitures SARL
ICE: 001234567890123 | IF: 12345678 | RC 45678 Casa
FACTURE N: FAC-2026-777
Date: 15/03/2026
Client: Atlas Negoce SARL
ICE Client: 009876543210987

Total HT: 1000.00 MAD
TVA 20% Base: 1000.00 Montant: 200.00
Total TTC: 1200.00 MAD
"""


def _h(sub: str | None, tenant: uuid.UUID | None = None) -> dict[str, str]:
    h = {"Idempotency-Key": str(uuid.uuid4())}
    if sub:
        h["Authorization"] = f"Bearer {sub}"
    if tenant:
        h["X-Tenant-Id"] = str(tenant)
    return h


@pytest.fixture
def env(db_conn: psycopg.Connection) -> dict:
    t1 = seed_tenant(db_conn, "Cabinet Upload Un")
    acc = f"acc-{uuid.uuid4()}"
    acc_id = seed_user(db_conn, identity_subject=acc, email=f"{acc}@a.ma")
    seed_membership(db_conn, acc_id, t1, "accountant")
    cu = f"cu-{uuid.uuid4()}"
    cu_id = seed_user(db_conn, identity_subject=cu, email=f"{cu}@c.ma")
    cu_m = seed_membership(db_conn, cu_id, t1, "client_user")
    t2 = seed_tenant(db_conn, "Cabinet Upload Deux")
    other = f"other-{uuid.uuid4()}"
    other_id = seed_user(db_conn, identity_subject=other, email=f"{other}@b.ma")
    seed_membership(db_conn, other_id, t2, "accountant")

    set_rls_context(db_conn, t1, acc_id)
    c_in = create_client_entity(db_conn, t1, "Societe Upload In", str(acc_id), ice="001122334455801").id
    c_out = create_client_entity(db_conn, t1, "Societe Upload Out", str(acc_id), ice="001122334455802").id
    seed_client_scope(db_conn, t1, cu_m, c_in)
    p = open_accounting_period(
        db_conn, t1, c_out, str(acc_id), "2026-03",
        datetime.date(2026, 3, 1), datetime.date(2026, 3, 31), datetime.date(2026, 12, 31),
    )["id"]
    wr = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
               VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'intake');""",
            (wr, t1, c_out, p),
        )
    db_conn.commit()
    return {"t1": t1, "acc": acc, "cu": cu, "other": other, "wr": wr}


def _init(client: TestClient, env: dict, data: bytes) -> str:
    r = client.post(
        f"/v1/work-requests/{env['wr']}/uploads",
        headers=_h(env["acc"], env["t1"]),
        json={
            "original_filename": "facture.pdf",
            "byte_size": len(data),
            "mime_type": "application/pdf",
            "sha256": hashlib.sha256(data).hexdigest(),
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["document_id"]


def _put(client: TestClient, doc: str, data: bytes, headers: dict):
    return client.put(f"/v1/documents/{doc}/content", content=data, headers={**headers, "Content-Type": "application/octet-stream"})


def test_upload_then_process_over_http_only(env):
    c = TestClient(app)
    data = INVOICE + uuid.uuid4().hex.encode()
    doc = _init(c, env, data)
    r = _put(c, doc, data, _h(env["acc"], env["t1"]))
    assert r.status_code == 200, r.text
    assert r.json()["sha256"] == hashlib.sha256(data).hexdigest()
    done = c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(env["acc"], env["t1"]))
    assert done.status_code == 200, done.text
    assert done.json()["extraction_id"]


def test_original_is_write_once(env):
    c = TestClient(app)
    data = INVOICE + uuid.uuid4().hex.encode()
    doc = _init(c, env, data)
    assert _put(c, doc, data, _h(env["acc"], env["t1"])).status_code == 200
    assert _put(c, doc, data, _h(env["acc"], env["t1"])).status_code == 409


def test_bytes_must_match_declared_size_and_hash(env):
    c = TestClient(app)
    data = INVOICE + uuid.uuid4().hex.encode()
    doc = _init(c, env, data)
    tampered = data[:-1] + (b"X" if data[-1:] != b"X" else b"Y")
    assert _put(c, doc, tampered, _h(env["acc"], env["t1"])).status_code == 422  # same size, other hash
    assert _put(c, doc, data[:-1], _h(env["acc"], env["t1"])).status_code == 422  # shorter
    assert _put(c, doc, data + b"!", _h(env["acc"], env["t1"])).status_code == 413  # longer
    assert _put(c, doc, data, _h(env["acc"], env["t1"])).status_code == 200  # nothing was stored before


def test_scope_first_404_and_401(env):
    c = TestClient(app)
    data = INVOICE + uuid.uuid4().hex.encode()
    doc = _init(c, env, data)
    assert _put(c, doc, data, _h(env["other"], env["t1"])).status_code == 404
    assert _put(c, doc, data, _h(env["other"])).status_code == 404
    assert _put(c, doc, data, _h(env["cu"], env["t1"])).status_code == 404  # client user, company out of scope
    assert _put(c, str(uuid.uuid4()), data, _h(env["acc"], env["t1"])).status_code == 404
    assert _put(c, doc, data, _h(None)).status_code == 401
