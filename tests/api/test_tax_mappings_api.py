"""Client tax mappings API (Phase 3 completion) and the path real document -> proposal.

Rules: scope-first 404; client users refused; only members with a professional registration
approve (human decision 6 Nov 2026); unapproved mappings are never used (Part K 15).
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.accounting.service import seed_cgnc_chart
from avenel.tenancy.auth import set_rls_context
from tests.api.test_document_reading_real_pdf import _h, _pdf, _upload, env  # noqa: F401
from tests.helpers import seed_client_scope, seed_membership, seed_user


@pytest.fixture
def mp(env, db_conn: psycopg.Connection) -> dict:  # noqa: F811
    """Adds a registered professional, a client user, and the CGNC chart to the reading env."""
    t = env["t"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT client_entity_id FROM work_requests WHERE id = %s;", (env["wr"],))
        client_id = cur.fetchone()[0]
    expert = f"expert-{uuid.uuid4()}"
    eid = seed_user(db_conn, identity_subject=expert, email=f"{expert}@a.ma")
    seed_membership(db_conn, eid, t, "accountant", professional_title="expert_comptable",
                    professional_registration_no=f"OEC-{uuid.uuid4().hex[:6]}")
    cu = f"cu-{uuid.uuid4()}"
    cm = seed_membership(db_conn, seed_user(db_conn, identity_subject=cu, email=f"{cu}@c.ma"), t, "client_user")
    seed_client_scope(db_conn, t, cm, client_id)
    set_rls_context(db_conn, t, eid)
    seed_cgnc_chart(db_conn, t, client_id, str(eid))
    db_conn.commit()
    return {**env, "client": client_id, "expert": expert, "cu": cu}


def _account_id(c: TestClient, mp: dict, code: str) -> str:
    items = c.get(f"/v1/client-entities/{mp['client']}/chart-accounts", headers=_h(mp["sub"], mp["t"])).json()["items"]
    return next(a["id"] for a in items if a["account_code"] == code)


def _put(c, mp, sub, tax_code, direction, account_id, tenant=None):
    return c.put(
        f"/v1/client-entities/{mp['client']}/tax-mappings",
        headers=_h(sub, tenant if tenant is not None else mp["t"]),
        json={"tax_code": tax_code, "direction": direction, "account_id": account_id},
    )


def test_slots_come_from_the_pack(mp):
    c = TestClient(app)
    r = c.get(f"/v1/client-entities/{mp['client']}/tax-mappings", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 200, r.text
    slots = {(i["tax_code"], i["direction"]) for i in r.json()["items"]}
    assert ("STANDARD_20", "purchase") in slots and ("WITHHOLDING", "withholding") in slots
    assert r.json()["can_approve"] is False  # plain accountant


def test_only_registered_professionals_approve(mp):
    c = TestClient(app)
    acc = _account_id(c, mp, "34552")
    r = _put(c, mp, mp["sub"], "STANDARD_20", "purchase", acc)
    assert r.status_code == 200, r.text
    assert r.json()["approved"] is False
    r = _put(c, mp, mp["expert"], "STANDARD_20", "purchase", acc)
    assert r.json()["approved"] is True
    # a later change by a non-professional withdraws the approval
    r = _put(c, mp, mp["sub"], "STANDARD_20", "purchase", _account_id(c, mp, "34551"))
    assert r.json()["approved"] is False


def test_rejects_unknown_slot_and_foreign_account(mp):
    c = TestClient(app)
    acc = _account_id(c, mp, "34552")
    assert _put(c, mp, mp["expert"], "MADE_UP_7", "purchase", acc).status_code == 422
    assert _put(c, mp, mp["expert"], "STANDARD_20", "sideways", acc).status_code == 422
    assert _put(c, mp, mp["expert"], "STANDARD_20", "purchase", str(uuid.uuid4())).status_code == 422


def test_scope_rules(mp):
    c = TestClient(app)
    acc = _account_id(c, mp, "34552")
    assert _put(c, mp, mp["other"], "STANDARD_20", "purchase", acc).status_code == 404
    assert _put(c, mp, mp["other"], "STANDARD_20", "purchase", acc, tenant="").status_code == 404
    assert _put(c, mp, mp["cu"], "STANDARD_20", "purchase", acc).status_code == 403
    assert c.get(f"/v1/client-entities/{mp['client']}/tax-mappings", headers=_h(mp["cu"], mp["t"])).status_code == 403
    assert _put(c, mp, None, "STANDARD_20", "purchase", acc).status_code == 401


def _read_scanned(c, mp) -> str:
    doc = _upload(c, mp, _pdf(scanned=True))
    assert c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(mp["sub"], mp["t"])).status_code == 200
    return doc


def test_unapproved_mapping_is_never_used(mp):
    c = TestClient(app)
    _put(c, mp, mp["sub"], "STANDARD_20", "purchase", _account_id(c, mp, "34552"))
    doc = _read_scanned(c, mp)
    r = c.post(f"/v1/documents/{doc}:generate-proposal", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "blocked" and r.json()["issue_code"] == "ACCOUNT_UNMAPPED"


def test_real_document_becomes_a_balanced_proposal_with_evidence(mp):
    c = TestClient(app)
    assert _put(c, mp, mp["expert"], "STANDARD_20", "purchase", _account_id(c, mp, "34552")).json()["approved"]
    doc = _read_scanned(c, mp)
    r = c.post(f"/v1/documents/{doc}:generate-proposal", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 200, r.text
    p = r.json()
    assert p.get("status") != "blocked", p
    lines = p["lines"]
    debit = round(sum(float(x.get("debit_mad") or 0) for x in lines), 2)
    credit = round(sum(float(x.get("credit_mad") or 0) for x in lines), 2)
    assert debit == credit == 12000.0, lines  # Part C.4 #3: balances, at least two lines
    assert len(lines) >= 2
    vat = [x for x in lines if str(x.get("account_code", "")).startswith("3455")]
    assert vat and float(vat[0]["debit_mad"]) == 2000.0  # read from the invoice, not computed
    for x in lines:  # Part K 16: every line points to a region of the source document
        refs = x.get("evidence_refs") or []
        assert any(ref.get("document_id") and ref.get("bbox") for ref in refs), x


def _proposal(c, mp) -> dict:
    assert _put(c, mp, mp["expert"], "STANDARD_20", "purchase", _account_id(c, mp, "34552")).json()["approved"]
    doc = _read_scanned(c, mp)
    return c.post(f"/v1/documents/{doc}:generate-proposal", headers=_h(mp["sub"], mp["t"])).json()


def _line_input(x: dict, **over) -> dict:
    keep = ("account_id", "account_code", "counterparty_id", "label", "currency", "debit_tx", "credit_tx",
            "fx_rate", "debit_mad", "credit_mad", "tax_code", "evidence_refs")
    return {**{k: x.get(k) for k in keep if x.get(k) is not None}, **over}


def test_edit_keeps_evidence_and_creates_a_revision(mp):
    c = TestClient(app)
    p = _proposal(c, mp)
    lines = [_line_input(x) for x in p["lines"]]
    lines[0]["label"] = "Fournitures de bureau (corrigé)"
    r = c.put(f"/v1/proposals/{p['proposal_id'] if 'proposal_id' in p else p['id']}", headers=_h(mp["sub"], mp["t"]), json={"lines": lines})
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == 2


def test_edit_without_evidence_is_refused(mp):
    c = TestClient(app)
    p = _proposal(c, mp)
    lines = [_line_input(x) for x in p["lines"]]
    lines[0]["evidence_refs"] = []
    r = c.put(f"/v1/proposals/{p['proposal_id'] if 'proposal_id' in p else p['id']}", headers=_h(mp["sub"], mp["t"]), json={"lines": lines})
    assert r.status_code == 422, r.text
    assert "justificative" in r.json()["detail"]


def test_edit_with_both_sides_is_a_422_not_a_crash(mp):
    c = TestClient(app)
    p = _proposal(c, mp)
    lines = [_line_input(x) for x in p["lines"]]
    lines[0]["debit_tx"] = 0
    lines[0]["credit_tx"] = 0
    r = c.put(f"/v1/proposals/{p['proposal_id'] if 'proposal_id' in p else p['id']}", headers=_h(mp["sub"], mp["t"]), json={"lines": lines})
    assert r.status_code == 422, r.text
