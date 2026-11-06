"""Phase 6b lettrage through the HTTP API, with the API connected as avenel_app (forced RLS)."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.api.test_document_reading_real_pdf import _h
from tests.helpers import seed_client_scope, seed_membership, seed_tenant, seed_user
from tests.lettrage.seed import Ledger


def _ledger(db_conn: psycopg.Connection) -> tuple[Ledger, dict]:
    lg = Ledger(db_conn)
    cp = lg.counterparty("Client Souss", "customer")
    inv = lg.sale(cp, 2, "FAC-2026-0101", "12000.00")
    lg.receipt(cp, 10, "VIR SOUSS FAC-2026-0101", "5000.00")
    lg.receipt(cp, 25, "VIR SOUSS SOLDE", "7000.00")
    db_conn.commit()
    return lg, {"cp": cp, "inv": inv}


def test_generate_accept_reverse_through_api(db_conn: psycopg.Connection):
    lg, _ = _ledger(db_conn)
    c = TestClient(app)
    h = lambda: _h(lg.sub, lg.tenant_id)
    r = c.get(f"/v1/clients/{lg.client_id}/open-items", params={"account_class": "customer"}, headers=h())
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 3 and r.json()["balances"][0]["balance_mad"] == "0.00"

    r = c.post(f"/v1/clients/{lg.client_id}/lettrage-groups:generate", headers=h())
    assert r.status_code == 200, r.text
    groups = r.json()
    assert len(groups) == 1 and groups[0]["kind"] == "split" and groups[0]["status"] == "proposed"
    gid = groups[0]["id"]

    r = c.post(f"/v1/lettrage-groups/{gid}:accept", headers=h())
    assert r.status_code == 200, r.text
    assert r.json()["letter_code"] == "A"
    # Accepting twice is refused.
    assert c.post(f"/v1/lettrage-groups/{gid}:accept", headers=h()).status_code == 409

    r = c.get(f"/v1/clients/{lg.client_id}/open-items", params={"account_class": "customer"}, headers=h())
    assert r.json()["items"] == []

    assert c.post(f"/v1/lettrage-groups/{gid}:reverse", headers=h(), json={"reason": ""}).status_code == 422
    r = c.post(f"/v1/lettrage-groups/{gid}:reverse", headers=h(), json={"reason": "Erreur d'affectation"})
    assert r.status_code == 200 and r.json()["status"] == "reversed"
    r = c.get(f"/v1/clients/{lg.client_id}/open-items", params={"account_class": "customer"}, headers=h())
    assert len(r.json()["items"]) == 3

    r = c.get(f"/v1/clients/{lg.client_id}/lettrage-groups", params={"status": "reversed"}, headers=h())
    assert [g["id"] for g in r.json()] == [gid]


def test_manual_group_unbalanced_is_409(db_conn: psycopg.Connection):
    lg, _ = _ledger(db_conn)
    c = TestClient(app)
    items = c.get(f"/v1/clients/{lg.client_id}/open-items", params={"account_class": "customer"},
                  headers=_h(lg.sub, lg.tenant_id)).json()["items"]
    inv = next(i for i in items if i["side"] == "debit")
    rec = next(i for i in items if i["side"] == "credit" and i["amount_mad"] == "5000.00")
    r = c.post(f"/v1/clients/{lg.client_id}/lettrage-groups", headers=_h(lg.sub, lg.tenant_id),
               json={"allocations": [{"journal_line_id": inv["journal_line_id"], "amount_mad": "6000.00"},
                                     {"journal_line_id": rec["journal_line_id"], "amount_mad": "5000.00"}]})
    assert r.status_code == 409 and "déséquilibré" in r.json()["detail"]
    r = c.post(f"/v1/clients/{lg.client_id}/lettrage-groups", headers=_h(lg.sub, lg.tenant_id),
               json={"allocations": [{"journal_line_id": inv["journal_line_id"], "amount_mad": "5000.00"},
                                     {"journal_line_id": rec["journal_line_id"], "amount_mad": "5000.00"}]})
    assert r.status_code == 201 and r.json()["kind"] == "manual"


def test_other_tenant_sees_nothing(db_conn: psycopg.Connection):
    lg, _ = _ledger(db_conn)
    t2 = seed_tenant(db_conn, "Cabinet Autre")
    other = f"other-{uuid.uuid4()}"
    seed_membership(db_conn, seed_user(db_conn, identity_subject=other, email=f"{other}@b.ma"), t2, "accountant")
    c = TestClient(app)
    gid = c.post(f"/v1/clients/{lg.client_id}/lettrage-groups:generate", headers=_h(lg.sub, lg.tenant_id)).json()[0]["id"]
    assert c.get(f"/v1/clients/{lg.client_id}/open-items", params={"account_class": "customer"},
                 headers=_h(other, t2)).status_code == 404
    assert c.get(f"/v1/lettrage-groups/{gid}", headers=_h(other, t2)).status_code == 404
    assert c.post(f"/v1/lettrage-groups/{gid}:accept", headers=_h(other, t2)).status_code == 404


def test_roles(db_conn: psycopg.Connection):
    lg, _ = _ledger(db_conn)
    c = TestClient(app)
    op = f"op-{uuid.uuid4()}"
    op_uid = seed_user(db_conn, identity_subject=op, email=f"{op}@a.ma")
    with db_conn.cursor() as cur:
        cur.execute("""INSERT INTO memberships (tenant_id, user_id, role, status, operator_access_expires_at)
                       VALUES (%s, %s, 'operator', 'active', now() + interval '1 day')""", (lg.tenant_id, op_uid))
    cu = f"cu-{uuid.uuid4()}"
    mid = seed_membership(db_conn, seed_user(db_conn, identity_subject=cu, email=f"{cu}@a.ma"), lg.tenant_id, "client_user")
    seed_client_scope(db_conn, lg.tenant_id, mid, lg.client_id)
    db_conn.commit()
    url = f"/v1/clients/{lg.client_id}/open-items"
    assert c.get(url, params={"account_class": "customer"}, headers=_h(op, lg.tenant_id)).status_code == 200
    assert c.post(f"/v1/clients/{lg.client_id}/lettrage-groups:generate", headers=_h(op, lg.tenant_id)).status_code == 403
    assert c.get(url, params={"account_class": "customer"}, headers=_h(cu, lg.tenant_id)).status_code == 403
