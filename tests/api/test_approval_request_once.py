"""D-24 (founder's decision, 19 Nov 2026): one pending request for approval per monthly file.

A second request while one is pending answers 409 and changes nothing; it used to answer 500. Once the pending
request is decided (here: rejected, which sends the file back to preparation), a new request is accepted.
"""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.api.test_approval_export_api import _decide, _request_approval
from tests.api.test_document_reading_real_pdf import _h, env  # noqa: F401
from tests.api.test_tax_mappings_api import _proposal, mp  # noqa: F401


def _approvals(db_conn: psycopg.Connection, wr) -> list[tuple]:
    db_conn.rollback()
    return db_conn.execute("SELECT status FROM approvals WHERE work_request_id = %s ORDER BY revision;",
                           (wr,)).fetchall()


def test_a_second_request_while_one_is_pending_is_refused(mp, db_conn):  # noqa: F811
    c = TestClient(app)
    _proposal(c, mp)
    first = _request_approval(c, mp)

    r = c.post(f"/v1/work-requests/{mp['wr']}/approvals", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 409, r.text
    assert "déjà en attente" in r.json()["detail"]
    assert _approvals(db_conn, mp["wr"]) == [("pending",)]
    assert c.get(f"/v1/work-requests/{mp['wr']}", headers=_h(mp["sub"], mp["t"])).json()["status"] == "awaiting_approval"
    # The pending request is still the one the expert can decide.
    assert _decide(c, mp, mp["expert"], first).status_code == 200


def test_after_a_rejection_a_new_request_is_accepted(mp, db_conn):  # noqa: F811
    c = TestClient(app)
    _proposal(c, mp)
    first = _request_approval(c, mp)
    assert _decide(c, mp, mp["expert"], first, decision="rejected").status_code == 200
    assert c.get(f"/v1/work-requests/{mp['wr']}", headers=_h(mp["sub"], mp["t"])).json()["status"] == "preparing"

    second = c.post(f"/v1/work-requests/{mp['wr']}/approvals", headers=_h(mp["sub"], mp["t"]))
    assert second.status_code == 201, second.text
    assert _approvals(db_conn, mp["wr"]) == [("rejected",), ("pending",)]
