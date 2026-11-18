"""Phase 8a: GET /v1/work-requests/{id}/agent-tasks shows the agents' work to firm staff only."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.tenancy.auth import set_rls_context
from avenel.workforce.orchestrator import record_task
from tests.api.test_document_reading_real_pdf import _h, env  # noqa: F401
from tests.api.test_tax_mappings_api import mp  # noqa: F401


def test_staff_see_the_agent_tasks_client_users_and_other_firms_do_not(mp, db_conn: psycopg.Connection):  # noqa: F811
    t, wr = mp["t"], uuid.UUID(str(mp["wr"]))
    set_rls_context(db_conn, t)
    record_task(db_conn, None, t, wr, "orchestrator", "finish", "escalated", "human", {"blocking_issues": 2})
    db_conn.commit()
    c = TestClient(app)

    r = c.get(f"/v1/work-requests/{wr}/agent-tasks", headers=_h(mp["sub"], t))
    assert r.status_code == 200, r.text
    [task] = r.json()["items"]
    assert (task["agent"], task["outcome"], task["handed_off_to"]) == ("orchestrator", "escalated", "human")
    assert task["summary"] == {"blocking_issues": 2}

    assert c.get(f"/v1/work-requests/{wr}/agent-tasks", headers=_h(mp["cu"], t)).status_code == 404
    assert c.get(f"/v1/work-requests/{wr}/agent-tasks", headers=_h(mp["other"])).status_code == 404


def test_a_document_gets_one_active_proposal_even_if_proposed_twice(mp, db_conn: psycopg.Connection):  # noqa: F811
    """Real stack, 17 Nov 2026: the bookkeeping agent proposed, then a click created a second active entry."""
    from tests.api.test_tax_mappings_api import _proposal

    c = TestClient(app)
    first = _proposal(c, mp)
    assert first.get("id"), first
    doc = db_conn.execute("SELECT source_document_id FROM journal_proposals WHERE id = %s;", (first["id"],)).fetchone()[0]

    r = c.post(f"/v1/documents/{doc}:generate-proposal", headers=_h(mp["sub"], mp["t"]))
    assert r.status_code == 409, r.text
    active = db_conn.execute(
        "SELECT count(*) FROM journal_proposals WHERE source_document_id = %s AND status NOT IN ('superseded', 'rejected');",
        (doc,),
    ).fetchone()
    assert active == (1,)
