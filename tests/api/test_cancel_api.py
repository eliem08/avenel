"""Phase 8d: cancelling a monthly file (ARCHITECTURE.md D.1, docs/plans/phase-8d-cancel.md).

A manager cancels with a reason; the pending approval and queued jobs are cancelled; the file takes no more
documents and asks the client nothing more; the period may get a new file. Accountants, staff and client users
cannot cancel, and other firms cannot see the file.
"""

from __future__ import annotations

import json
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.jobs.queue import Job, enqueue
from avenel.jobs.worker import run_once
from avenel.tenancy.auth import set_rls_context
from avenel.workforce import orchestrator
from tests.api.test_document_reading_real_pdf import _h, _pdf, _upload, env  # noqa: F401
from tests.api.test_tax_mappings_api import _proposal, mp  # noqa: F401
from tests.helpers import seed_membership, seed_user


@pytest.fixture
def mgr(mp, db_conn: psycopg.Connection) -> dict:  # noqa: F811
    """Adds a firm manager to the API env."""
    sub = f"mgr-{uuid.uuid4()}"
    seed_membership(db_conn, seed_user(db_conn, identity_subject=sub, email=f"{sub}@a.ma"), mp["t"], "manager")
    db_conn.commit()
    return {**mp, "mgr": sub}


def _cancel(c: TestClient, env: dict, who: str, reason: str = "Le client a changé de cabinet.", tenant=True):
    return c.post(f"/v1/work-requests/{env['wr']}:cancel", headers=_h(who, env["t"] if tenant else None),
                  json={"reason": reason})


def _status(db_conn: psycopg.Connection, wr) -> str:
    db_conn.rollback()
    return db_conn.execute("SELECT status FROM work_requests WHERE id = %s;", (wr,)).fetchone()[0]


def test_a_manager_cancels_a_file_awaiting_approval(mgr, db_conn):
    c = TestClient(app)
    assert _proposal(c, mgr).get("id")
    db_conn.execute("UPDATE issues SET status = 'resolved', resolution = 'fixed', resolved_at = now() "
                    "WHERE work_request_id = %s;", (mgr["wr"],))
    db_conn.commit()
    r = c.post(f"/v1/work-requests/{mgr['wr']}/approvals", headers=_h(mgr["sub"], mgr["t"]))
    assert r.status_code == 201, r.text
    set_rls_context(db_conn, mgr["t"])
    doc = uuid.UUID(_upload(c, mgr, _pdf()))
    assert enqueue(db_conn, mgr["t"], mgr["wr"], "read_document", doc)
    db_conn.commit()

    r = _cancel(c, mgr, mgr["mgr"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"

    db_conn.rollback()
    w = mgr["wr"]
    row = db_conn.execute("SELECT a.status, u.identity_subject, a.reason, a.decided_at IS NOT NULL FROM approvals a "
                          "JOIN users u ON u.id = a.decided_by WHERE a.work_request_id = %s;", (w,)).fetchall()
    assert row == [("cancelled", mgr["mgr"], "Dossier annulé : Le client a changé de cabinet.", True)]
    assert db_conn.execute("SELECT status, finished_at IS NOT NULL FROM jobs WHERE work_request_id = %s "
                           "AND subject_id = %s;", (w, doc)).fetchall() == [("cancelled", True)]
    last = c.get(f"/v1/work-requests/{w}/status-history", headers=_h(mgr["sub"], mgr["t"])).json()["items"][-1]
    assert (last["from_status"], last["to_status"], last["reason"], last["actor_type"]) == (
        "awaiting_approval", "cancelled", "Le client a changé de cabinet.", "user")
    # Evidence is kept: the proposal is still there.
    assert db_conn.execute("SELECT count(*) FROM journal_proposals WHERE work_request_id = %s;", (w,)).fetchone()[0] >= 1


def test_the_manager_who_prepared_the_file_cannot_close_its_approval(mgr, db_conn):
    """Separation of duties (approvals check in 001) covers closing the approval, not only approving it."""
    c = TestClient(app)
    assert _proposal(c, mgr).get("id")
    db_conn.execute("UPDATE issues SET status = 'resolved', resolution = 'fixed', resolved_at = now() "
                    "WHERE work_request_id = %s;", (mgr["wr"],))
    db_conn.commit()
    assert c.post(f"/v1/work-requests/{mgr['wr']}/approvals", headers=_h(mgr["mgr"], mgr["t"])).status_code == 201
    r = _cancel(c, mgr, mgr["mgr"])
    assert r.status_code == 409, r.text
    assert "un autre responsable" in r.json()["detail"]
    assert _status(db_conn, mgr["wr"]) == "awaiting_approval"
    assert db_conn.execute("SELECT status FROM approvals WHERE work_request_id = %s;", (mgr["wr"],)).fetchall() == [
        ("pending",)]


def test_only_owner_and_manager_may_cancel_and_other_firms_do_not_see_the_file(mgr, db_conn):
    c = TestClient(app)
    assert _cancel(c, mgr, mgr["sub"]).status_code == 403  # accountant
    assert _cancel(c, mgr, mgr["expert"]).status_code == 403  # accountant, registered professional
    assert _cancel(c, mgr, mgr["cu"]).status_code == 404  # client user: the internal action does not exist
    assert _cancel(c, mgr, mgr["other"], tenant=False).status_code == 404  # another firm
    assert _cancel(c, mgr, mgr["mgr"], reason="").status_code == 422  # a reason is required
    assert _cancel(c, mgr, mgr["mgr"], reason="   ").status_code == 409  # blank after trimming
    assert _status(db_conn, mgr["wr"]) == "intake"


def test_a_cancelled_file_takes_nothing_more_and_its_period_gets_a_new_file(mgr, db_conn):
    c = TestClient(app)
    assert _cancel(c, mgr, mgr["mgr"]).status_code == 200
    again = _cancel(c, mgr, mgr["mgr"])
    assert again.status_code == 409 and again.json()["type"] == "avenel/workflow-transition-refused"

    up = c.post(f"/v1/work-requests/{mgr['wr']}/uploads", headers=_h(mgr["sub"], mgr["t"]),
                json={"original_filename": "f.pdf", "byte_size": 10, "mime_type": "application/pdf", "sha256": "a" * 64})
    assert up.status_code == 409, up.text

    db_conn.rollback()
    period = db_conn.execute("SELECT accounting_period_id FROM work_requests WHERE id = %s;", (mgr["wr"],)).fetchone()[0]
    new = c.post("/v1/work-requests", headers=_h(mgr["sub"], mgr["t"]),
                 json={"client_entity_id": str(mgr["client"]), "accounting_period_id": str(period)})
    assert new.status_code == 201, new.text
    assert new.json()["status"] == "draft"


def test_the_client_is_asked_nothing_more_on_a_cancelled_file(mgr, db_conn):
    c = TestClient(app)
    set_rls_context(db_conn, mgr["t"])
    issue = db_conn.execute(
        "INSERT INTO issues (tenant_id, client_entity_id, work_request_id, code, severity, status, evidence_refs) "
        "VALUES (%s, %s, %s, 'MISSING_DOCUMENT', 'review', 'waiting_client', %s::jsonb) RETURNING id;",
        (mgr["t"], mgr["client"], mgr["wr"], json.dumps([{"type": "client_request", "prompt": "Merci d'envoyer le relevé."}])),
    ).fetchone()[0]
    db_conn.commit()
    listed = c.get("/v1/portal/requests", headers=_h(mgr["cu"], mgr["t"])).json()
    assert str(issue) in json.dumps(listed)

    assert _cancel(c, mgr, mgr["mgr"]).status_code == 200
    listed = c.get("/v1/portal/requests", headers=_h(mgr["cu"], mgr["t"])).json()
    assert str(issue) not in json.dumps(listed)
    r = c.post(f"/v1/portal/requests/{issue}:answer", headers=_h(mgr["cu"], mgr["t"]), json={"response": "Voici."})
    assert r.status_code == 404, r.text
    db_conn.rollback()
    assert db_conn.execute("SELECT status FROM issues WHERE id = %s;", (issue,)).fetchone()[0] == "waiting_client"


def test_a_job_of_a_cancelled_file_is_not_run(mgr, db_conn, postgres_url):
    c = TestClient(app)
    db_conn.execute("UPDATE jobs SET status = 'failed', locked_at = NULL, finished_at = now() "
                    "WHERE status IN ('queued','running')")  # nothing else due
    set_rls_context(db_conn, mgr["t"])
    doc = uuid.UUID(_upload(c, mgr, _pdf()))
    assert enqueue(db_conn, mgr["t"], mgr["wr"], "read_document", doc)
    db_conn.commit()
    # Cancelled straight in the table, as if the cancel had come between queueing and the worker's claim.
    db_conn.execute("UPDATE work_requests SET status = 'cancelled' WHERE id = %s;", (mgr["wr"],))
    db_conn.execute("UPDATE jobs SET status = 'queued' WHERE subject_id = %s;", (doc,))
    db_conn.commit()

    ran: list[Job] = []
    assert run_once(postgres_url, {"read_document": lambda conn, job: ran.append(job)}) == "cancelled"
    assert ran == []
    db_conn.rollback()
    assert db_conn.execute("SELECT status, locked_at IS NULL FROM jobs WHERE subject_id = %s;", (doc,)).fetchone() == (
        "cancelled", True)


def test_a_step_that_finishes_after_the_cancel_hands_nothing_on(mgr, db_conn):
    c = TestClient(app)
    set_rls_context(db_conn, mgr["t"])
    doc = uuid.UUID(_upload(c, mgr, _pdf()))
    db_conn.execute("UPDATE work_requests SET status = 'cancelled' WHERE id = %s;", (mgr["wr"],))
    job_id = db_conn.execute(
        "INSERT INTO jobs (tenant_id, work_request_id, step, subject_id, revision, status, locked_at, attempts) "
        "VALUES (%s, %s, 'read_document', %s, 1, 'running', now(), 1) RETURNING id;",
        (mgr["t"], mgr["wr"], doc),
    ).fetchone()[0]
    orchestrator.after_step(db_conn, Job(job_id, mgr["t"], mgr["wr"], "read_document", doc, 1), {})
    assert db_conn.execute("SELECT count(*) FROM jobs WHERE work_request_id = %s AND step = 'prepare_proposals';",
                           (mgr["wr"],)).fetchone()[0] == 0
    assert db_conn.execute("SELECT status FROM work_requests WHERE id = %s;", (mgr["wr"],)).fetchone()[0] == "cancelled"
    db_conn.rollback()
