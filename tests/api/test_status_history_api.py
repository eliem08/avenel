"""Phase 8c through the API: a firm member's upload submits the monthly file, the status history is shown to
firm staff only, and a refused status change answers 409."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from tests.api.test_document_reading_real_pdf import _h, _pdf, _upload, env  # noqa: F401
from tests.api.test_tax_mappings_api import _proposal, mp  # noqa: F401


def _set_status(db_conn: psycopg.Connection, wr: uuid.UUID, status: str) -> None:
    db_conn.execute("UPDATE work_requests SET status = %s WHERE id = %s;", (status, wr))
    db_conn.commit()


def test_a_firm_upload_submits_the_file_and_staff_see_the_history(mp, db_conn):  # noqa: F811
    _set_status(db_conn, mp["wr"], "draft")
    c = TestClient(app)
    doc = _upload(c, mp, _pdf(scanned=False))
    assert c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(mp["sub"], mp["t"])).status_code == 200

    r = c.get(f"/v1/work-requests/{mp['wr']}/status-history", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [(i["from_status"], i["to_status"]) for i in items] == [("draft", "intake"), ("intake", "extracting")]
    assert {i["actor_type"] for i in items} == {"user"}
    assert c.get(f"/v1/work-requests/{mp['wr']}", headers=_h(mp["sub"], mp["t"])).json()["status"] == "extracting"

    assert c.get(f"/v1/work-requests/{mp['wr']}/status-history", headers=_h(mp["cu"], mp["t"])).status_code == 404
    assert c.get(f"/v1/work-requests/{mp['wr']}/status-history", headers=_h(mp["other"])).status_code == 404


def test_a_refused_status_change_answers_409_and_changes_nothing(mp, db_conn):  # noqa: F811
    c = TestClient(app)
    assert _proposal(c, mp).get("id")
    # Setup: the issues found on the scan are settled, so the request reaches the status check.
    db_conn.execute("UPDATE issues SET status = 'resolved', resolution = 'fixed', resolved_at = now() "
                    "WHERE work_request_id = %s;", (mp["wr"],))
    _set_status(db_conn, mp["wr"], "completed")  # an exported file cannot be sent for approval again

    r = c.post(f"/v1/work-requests/{mp['wr']}/approvals", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 409, r.text
    assert r.json()["type"] == "avenel/workflow-transition-refused", r.text
    assert "completed" in r.json()["detail"]
    db_conn.rollback()
    assert db_conn.execute("SELECT status FROM work_requests WHERE id = %s;", (mp["wr"],)).fetchone() == ("completed",)
    assert db_conn.execute("SELECT count(*) FROM approvals WHERE work_request_id = %s;", (mp["wr"],)).fetchone() == (0,)


def test_the_file_list_carries_the_client_name(mp):  # noqa: F811
    """Seen on the stack: the queue took names from /client-entities (first 50 only), so with more clients
    older files showed "—" and could not be found by name."""
    c = TestClient(app)
    items = c.get("/v1/work-requests", headers=_h(mp["sub"], mp["t"])).json()["items"]
    mine = next(i for i in items if i["id"] == str(mp["wr"]))
    assert mine["client_legal_name"] == "Atlas Distribution SARL"
