"""Phase 5 completion: approval and export through the HTTP API, from a real read document.

Path: scanned invoice -> proposal (prepared by an accountant) -> approval requested -> decided
by a registered professional with fresh MFA -> export file + evidence pack. Also: segregation
of duties, MFA freshness, scope, and export refused after the file changed (subject hash).
"""

from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient

from apps.api.main import app
from tests.api.test_document_reading_real_pdf import _h, env  # noqa: F401
from tests.api.test_tax_mappings_api import _line_input, _proposal, mp  # noqa: F401


def _mfa(sub: str, tenant, fresh: bool = True) -> dict[str, str]:
    h = _h(sub, tenant)
    h["X-MFA-Authenticated"] = "true" if fresh else "false"
    h["X-Auth-Time"] = str(int(time.time()) - (0 if fresh else 3600))
    return h


def _acknowledge_review_issues(c: TestClient, mp: dict) -> int:  # noqa: F811
    """A person acknowledges each open review issue with a reason (the approval rule requires it)."""
    items = c.get(f"/v1/work-requests/{mp['wr']}/issues", headers=_h(mp["sub"], mp["t"])).json()["items"]
    n = 0
    for i in items:
        if i["severity"] == "review" and i["status"] == "open":
            r = c.post(f"/v1/issues/{i['id']}:acknowledge", headers=_h(mp["sub"], mp["t"]),
                       json={"resolution_note": "Compte vérifié par le collaborateur"})
            assert r.status_code == 200, r.text
            n += 1
    return n


def _request_approval(c: TestClient, mp: dict) -> dict:  # noqa: F811
    _acknowledge_review_issues(c, mp)
    r = c.post(f"/v1/work-requests/{mp['wr']}/approvals", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 201, r.text
    return r.json()


def _decide(c, mp, sub, approval, fresh=True, decision="approved", subject_hash=None):  # noqa: F811
    return c.post(
        f"/v1/approvals/{approval['id'] if 'id' in approval else approval['approval_id']}:decide",
        headers=_mfa(sub, mp["t"], fresh),
        json={"decision": decision, "reason": "Contrôle effectué",
              "subject_hash": subject_hash or approval["subject_hash"]},
    )


def test_full_path_approval_then_export(mp):  # noqa: F811
    c = TestClient(app)
    _proposal(c, mp)  # prepared by the accountant (mp["sub"])
    ap = _request_approval(c, mp)
    assert len(ap["subject_hash"]) == 64

    # Segregation of duties: the preparer cannot approve (Part C.4 #8, K 23)
    assert _decide(c, mp, mp["sub"], ap).status_code in (403, 409)
    # A registered professional without fresh MFA is asked to re-authenticate (K 5)
    stale = _decide(c, mp, mp["expert"], ap, fresh=False)
    assert stale.status_code == 401
    assert "insufficient_user_authentication" in stale.headers.get("www-authenticate", "")
    # Client user and other tenant
    assert _decide(c, mp, mp["cu"], ap).status_code in (403, 404)
    assert _decide(c, mp, mp["other"], ap).status_code == 404
    # The registered professional with fresh MFA approves
    ok = _decide(c, mp, mp["expert"], ap)
    assert ok.status_code == 200, ok.text

    approval_id = ap["id"] if "id" in ap else ap["approval_id"]
    for target in ("sage100_csv", "sage100_pnm", "odoo_csv"):
        ex = c.post(f"/v1/work-requests/{mp['wr']}/exports", headers=_h(mp["expert"], mp["t"]),
                    json={"approval_id": approval_id, "target": target})
        assert ex.status_code == 201, (target, ex.text)
        export_id = ex.json()["id"] if "id" in ex.json() else ex.json()["export_id"]
        f = c.get(f"/v1/exports/{export_id}/file", headers=_h(mp["expert"], mp["t"]))
        assert f.status_code == 200, (target, f.text)
        assert b"12000" in f.content.replace(b",", b".").replace(b".00", b"").replace(b" ", b""), (target, f.content[:400])
        pack = c.get(f"/v1/exports/{export_id}/evidence-pack", headers=_h(mp["expert"], mp["t"]))
        assert pack.status_code == 200, (target, pack.text[:300])
        # other tenant cannot read the export
        assert c.get(f"/v1/exports/{export_id}/file", headers=_h(mp["other"])).status_code == 404


def test_export_refused_when_the_file_changed_after_approval(mp):  # noqa: F811
    from tests.api.test_tax_mappings_api import _read_scanned

    c = TestClient(app)
    p = _proposal(c, mp)
    ap = _request_approval(c, mp)
    assert _decide(c, mp, mp["expert"], ap).status_code == 200
    # Approved lines are immutable (Part C.4 #5): editing the approved entry is refused
    lines = [_line_input(x) for x in p["lines"]]
    lines[0]["label"] = "Modifié après validation"
    pid = p["proposal_id"] if "proposal_id" in p else p["id"]
    assert c.put(f"/v1/proposals/{pid}", headers=_h(mp["sub"], mp["t"]), json={"lines": lines}).status_code == 409
    # A new document proposed after approval changes the file's subject hash
    doc2 = _read_scanned(c, mp)
    gen = c.post(f"/v1/documents/{doc2}:generate-proposal", headers=_h(mp["sub"], mp["t"]))
    assert gen.status_code == 200 and gen.json().get("status") != "blocked", gen.text
    approval_id = ap["id"] if "id" in ap else ap["approval_id"]
    ex = c.post(f"/v1/work-requests/{mp['wr']}/exports", headers=_h(mp["expert"], mp["t"]),
                json={"approval_id": approval_id, "target": "sage100_csv"})
    assert ex.status_code == 409, ex.text  # Part C.4 #7, K 24 ApprovalStale


def test_decide_with_a_wrong_hash_is_refused(mp):  # noqa: F811
    c = TestClient(app)
    _proposal(c, mp)
    ap = _request_approval(c, mp)
    assert _decide(c, mp, mp["expert"], ap, subject_hash="0" * 64).status_code == 409


def test_unknown_approval_and_export_are_404(mp):  # noqa: F811
    c = TestClient(app)
    assert c.get(f"/v1/exports/{uuid.uuid4()}", headers=_h(mp["expert"], mp["t"])).status_code == 404
    assert _decide(c, mp, mp["expert"], {"id": str(uuid.uuid4()), "subject_hash": "0" * 64}).status_code == 404


def test_approval_refused_while_review_issues_are_open(mp):  # noqa: F811
    c = TestClient(app)
    _proposal(c, mp)
    r = c.post(f"/v1/work-requests/{mp['wr']}/approvals", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 409, r.text
    assert _acknowledge_review_issues(c, mp) >= 1
    assert c.post(f"/v1/work-requests/{mp['wr']}/approvals", headers=_h(mp["sub"], mp["t"])).status_code == 201


def test_who_generated_the_entries_cannot_approve_even_if_someone_else_requested(mp):  # noqa: F811
    """Part C.4 #8: the expert generates the entry, the accountant requests approval, the expert
    tries to approve -> refused. Before the fix only the requester was compared."""
    from tests.api.test_tax_mappings_api import _account_id, _put, _read_scanned

    c = TestClient(app)
    assert _put(c, mp, mp["expert"], "STANDARD_20", "purchase", _account_id(c, mp, "34552")).json()["approved"]
    doc = _read_scanned(c, mp)
    gen = c.post(f"/v1/documents/{doc}:generate-proposal", headers=_h(mp["expert"], mp["t"]))
    assert gen.status_code == 200 and gen.json().get("status") != "blocked", gen.text
    ap = _request_approval(c, mp)  # requested by the accountant
    r = _decide(c, mp, mp["expert"], ap)
    assert r.status_code in (403, 409), r.text
