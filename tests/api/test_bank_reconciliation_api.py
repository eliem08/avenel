"""Phase 4 completion: bank statements and reconciliation through the HTTP API.

Before Phase 4 completion every bank test called the service layer directly; none went
through the routes. These tests drive the routes with the API connected as avenel_app.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.bank.rib import compute_moroccan_rib_key
from avenel.documents.scanner import EICAR_SIGNATURE
from tests.api.test_document_reading_real_pdf import _h, env  # noqa: F401
from tests.api.test_tax_mappings_api import _account_id, _put, _read_scanned, mp  # noqa: F401
from tests.helpers import seed_membership, seed_tenant, seed_user

GOOD = """# Solde initial: 100000.00
# Solde final: 88000.00
Date,Libelle,Debit,Credit
2026-03-20,VIR FOURNISSEUR ATLAS FOURNITURES FAC-2026-0412,12000.00,0.00
"""
BROKEN = """# Solde initial: 100000.00
# Solde final: 90000.00
Date,Libelle,Debit,Credit
2026-03-20,VIR FOURNISSEUR ATLAS FOURNITURES,12000.00,0.00
"""


def _rib(seed: int) -> str:
    prefix = f"00778000{seed:014d}"
    return f"{prefix}{compute_moroccan_rib_key(prefix):02d}"


def _account(c: TestClient, mp: dict, sub: str | None = None) -> dict:  # noqa: F811
    r = c.post("/v1/bank-accounts", headers=_h(sub or mp["sub"], mp["t"]),
               json={"client_entity_id": str(mp["client"]), "rib": _rib(uuid.uuid4().int % 10**12)})
    assert r.status_code == 201, r.text
    return r.json()


def _upload(c: TestClient, mp: dict, account_id: str, content: bytes, name: str = "releve.csv", sub: str | None = None, tenant=None):  # noqa: F811
    return c.post(
        "/v1/bank-statements/upload",
        headers=_h(sub or mp["sub"], mp["t"] if tenant is None else tenant),
        data={"client_entity_id": str(mp["client"]), "bank_account_id": account_id, "work_request_id": str(mp["wr"])},
        files={"file": (name, content, "text/csv")},
    )


def test_statement_upload_parses_and_checks_balance(mp):  # noqa: F811
    c = TestClient(app)
    acc = _account(c, mp)
    assert acc["rib_masked"].endswith(acc["rib_last4"]) and "*" in acc["rib_masked"]
    r = _upload(c, mp, acc["id"], GOOD.encode())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("balance_check") == "ok", body


def test_balance_break_is_a_blocking_issue(mp):  # noqa: F811
    c = TestClient(app)
    acc = _account(c, mp)
    r = _upload(c, mp, acc["id"], BROKEN.encode())
    assert r.status_code in (201, 422), r.text
    issues = c.get(f"/v1/work-requests/{mp['wr']}/issues", headers=_h(mp["sub"], mp["t"])).json()["items"]
    assert any(i["severity"] == "blocking" and "BALANCE" in i["code"].upper() for i in issues), issues


def test_statement_upload_is_scanned_for_malware(mp):  # noqa: F811
    """Part K 8: every upload is scanned. A statement file is an upload like any other."""
    c = TestClient(app)
    acc = _account(c, mp)
    r = _upload(c, mp, acc["id"], EICAR_SIGNATURE + b"\n" + GOOD.encode())
    assert r.status_code == 422, r.text
    assert "quarantaine" in r.json()["detail"].lower()


def test_same_statement_twice_is_not_ingested_twice(mp):  # noqa: F811
    c = TestClient(app)
    acc = _account(c, mp)
    assert _upload(c, mp, acc["id"], GOOD.encode()).status_code == 201
    second = _upload(c, mp, acc["id"], GOOD.encode())
    assert second.status_code in (200, 409), second.text


def test_scope_rules(mp, db_conn: psycopg.Connection):  # noqa: F811
    c = TestClient(app)
    acc = _account(c, mp)
    # Another tenant cannot use this tenant's client or bank account
    assert _upload(c, mp, acc["id"], GOOD.encode(), sub=mp["other"]).status_code == 404
    # Client users cannot upload statements or register accounts
    assert _upload(c, mp, acc["id"], GOOD.encode(), sub=mp["cu"]).status_code == 403
    # A bank account of another client company cannot be used for this company
    t2 = seed_tenant(db_conn, "Cabinet Banque Autre")
    sub2 = f"acc2-{uuid.uuid4()}"
    seed_membership(db_conn, seed_user(db_conn, identity_subject=sub2, email=f"{sub2}@x.ma"), t2, "accountant")
    db_conn.commit()
    r = c.get(f"/v1/bank-accounts?client_entity_id={mp['client']}", headers=_h(sub2))
    assert r.status_code == 404 or r.json() == [], r.text


def test_payment_line_is_matched_to_the_invoice_and_accepted_once(mp):  # noqa: F811
    c = TestClient(app)
    assert _put(c, mp, mp["expert"], "STANDARD_20", "purchase", _account_id(c, mp, "34552")).json()["approved"]
    doc = _read_scanned(c, mp)
    gen = c.post(f"/v1/documents/{doc}:generate-proposal", headers=_h(mp["sub"], mp["t"]))
    assert gen.status_code == 200 and gen.json().get("status") != "blocked", gen.text
    acc = _account(c, mp)
    assert _upload(c, mp, acc["id"], GOOD.encode()).status_code == 201
    g = c.post("/v1/reconciliation/generate", headers=_h(mp["sub"], mp["t"]),
               json={"client_entity_id": str(mp["client"]), "work_request_id": str(mp["wr"])})
    assert g.status_code in (200, 201), g.text
    matches = c.get(f"/v1/reconciliation/matches?work_request_id={mp['wr']}", headers=_h(mp["sub"], mp["t"])).json()
    assert matches, "the 12 000,00 payment should have a candidate"
    m = matches[0]
    a = c.post(f"/v1/reconciliation/matches/{m['id']}/accept", headers=_h(mp["sub"], mp["t"]))
    assert a.status_code == 200, a.text
    again = c.post(f"/v1/reconciliation/matches/{m['id']}/accept", headers=_h(mp["sub"], mp["t"]))
    assert again.status_code in (200, 409), again.text
    # client user of the same company may read but not decide; other tenants see nothing
    assert c.post(f"/v1/reconciliation/matches/{m['id']}/reject", headers=_h(mp["cu"], mp["t"])).status_code == 403
    assert c.get(f"/v1/reconciliation/matches?work_request_id={mp['wr']}", headers=_h(mp["other"])).status_code == 404


def test_generate_refuses_a_client_that_is_not_the_work_requests(mp, db_conn: psycopg.Connection):  # noqa: F811
    from avenel.clients.service import create_client_entity
    from avenel.tenancy.auth import set_rls_context

    c = TestClient(app)
    with db_conn.cursor() as cur:
        cur.execute("SELECT user_id FROM memberships WHERE tenant_id = %s LIMIT 1;", (mp["t"],))
        uid = cur.fetchone()[0]
    set_rls_context(db_conn, mp["t"], uid)
    other_client = create_client_entity(db_conn, mp["t"], "Autre Societe SARL", str(uid), ice="001500000000777").id
    db_conn.commit()
    g = c.post("/v1/reconciliation/generate", headers=_h(mp["sub"], mp["t"]),
               json={"client_entity_id": str(other_client), "work_request_id": str(mp["wr"])})
    assert g.status_code == 404, g.text


def test_bank_transactions_of_a_file(mp):  # noqa: F811
    c = TestClient(app)
    acc = _account(c, mp)
    assert _upload(c, mp, acc["id"], GOOD.encode()).status_code == 201
    url = f"/v1/reconciliation/bank-transactions?work_request_id={mp['wr']}"
    r = c.get(url, headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["statements"][0]["balance_check"] == "ok"
    assert [i["amount"] for i in body["items"]] == [-12000.0]
    assert c.get(url, headers=_h(mp["other"])).status_code == 404
    assert c.get(url, headers=_h(None)).status_code == 401
