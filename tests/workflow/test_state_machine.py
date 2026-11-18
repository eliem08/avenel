"""Phase 8c: work_requests.status changes only along the D.1 graph, each edge with its guard, and every change
is in the audit trail. Real PostgreSQL, real approval and orchestrator services."""

from __future__ import annotations

import itertools
import uuid

import psycopg
import pytest

from avenel.approvals.service import (
    decide_work_request_approval,
    request_work_request_approval,
)
from avenel.tenancy.auth import set_rls_context
from avenel.workflow import state
from avenel.workflow.state import GuardFailed, TransitionNotAllowed
from avenel.workforce import orchestrator
from tests.approvals.test_approvals import approval_test_env  # noqa: F401 - fixture
from tests.reconciliation.test_reconciliation import recon_test_env  # noqa: F401 - fixture
from tests.workforce.test_orchestrator import _bank_statement, _job, _read_document


def _status(conn: psycopg.Connection, wr: uuid.UUID) -> tuple[str, int]:
    row = conn.execute("SELECT status, current_revision FROM work_requests WHERE id = %s;", (wr,)).fetchone()
    return row[0], row[1]


def _path(conn: psycopg.Connection, env: dict) -> list[str]:
    hist = state.history(conn, env["tenant_id"], env["work_request_id"])
    return [hist[0]["from_status"]] + [h["to_status"] for h in hist] if hist else []


@pytest.fixture
def draft_env(db_conn: psycopg.Connection, recon_test_env: dict) -> dict:  # noqa: F811
    """The reconciliation fixture's file, set back to draft (the fixture inserts it at 'intake')."""
    db_conn.execute("UPDATE work_requests SET status = 'draft' WHERE id = %s;", (recon_test_env["work_request_id"],))
    return recon_test_env


def _submit(conn: psycopg.Connection, env: dict) -> None:
    state.advance_to(conn, env["tenant_id"], env["work_request_id"], "extracting", "user", str(env["user_id"]),
                     "accountant", strict=True)


# ------------------------------------------------------------------------------------------- the graph

def test_only_the_d1_edges_are_allowed():
    expected = {
        ("draft", "intake"), ("intake", "extracting"), ("extracting", "preparing"), ("preparing", "reconciling"),
        ("reconciling", "quality_check"), ("quality_check", "needs_attention"),
        ("quality_check", "awaiting_approval"), ("needs_attention", "awaiting_approval"),
        ("awaiting_approval", "exporting"), ("awaiting_approval", "preparing"),
        ("exporting", "completed"), ("exporting", "completed_with_open_items"),
    }
    for frm, to in itertools.product(sorted(state.ALL_STATES), repeat=2):
        if to == "failed":
            want = True
        elif to == "cancelled":
            want = frm not in state.TERMINAL
        else:
            want = (frm, to) in expected
        assert state.allowed(frm, to) is want, (frm, to)


def test_an_edge_outside_the_graph_is_refused_and_nothing_is_written(db_conn, draft_env):
    env = draft_env
    _read_document(db_conn, env)
    with pytest.raises(TransitionNotAllowed):  # an approval needs the reading and preparation first
        state.transition(db_conn, env["tenant_id"], env["work_request_id"], "awaiting_approval", "user",
                         str(env["user_id"]), "accountant")
    with pytest.raises(TransitionNotAllowed):
        state.transition(db_conn, env["tenant_id"], env["work_request_id"], "completed", "user", str(env["user_id"]))
    assert _status(db_conn, env["work_request_id"])[0] == "draft"
    assert state.history(db_conn, env["tenant_id"], env["work_request_id"]) == []


# ------------------------------------------------------------------------------------------- guards

def test_submitting_needs_a_document_and_a_firm_member(db_conn, draft_env):
    env = draft_env
    t, w, u = env["tenant_id"], env["work_request_id"], str(env["user_id"])
    with pytest.raises(GuardFailed, match="Aucune pièce"):
        state.transition(db_conn, t, w, "intake", "user", u, "accountant")

    _read_document(db_conn, env)
    for actor_type, role in (("user", "client_user"), ("user", "operator"), ("agent", None)):
        with pytest.raises(GuardFailed, match="membre du cabinet"):
            state.transition(db_conn, t, w, "intake", actor_type, "agent:document" if role is None else u, role)
    assert _status(db_conn, w)[0] == "draft"

    state.transition(db_conn, t, w, "intake", "user", u, "accountant")
    submitted = db_conn.execute("SELECT submitted_at FROM work_requests WHERE id = %s;", (w,)).fetchone()[0]
    assert submitted is not None
    assert state.history(db_conn, t, w)[0] | {"occurred_at": None} == {
        "from_status": "draft", "to_status": "intake", "reason": None, "actor_type": "user", "actor_id": u,
        "occurred_at": None,
    }


def test_submitting_needs_an_open_period(db_conn, draft_env):
    env = draft_env
    _read_document(db_conn, env)
    db_conn.execute(
        "UPDATE accounting_periods SET status = 'closed' WHERE id = "
        "(SELECT accounting_period_id FROM work_requests WHERE id = %s);", (env["work_request_id"],)
    )
    with pytest.raises(GuardFailed, match="période"):
        _submit(db_conn, env)


def test_preparation_waits_until_every_document_is_read(db_conn, draft_env):
    env = draft_env
    _read_document(db_conn, env)
    other = _read_document(db_conn, env, status="processing")
    _submit(db_conn, env)
    with pytest.raises(GuardFailed, match="pas encore lues"):
        state.transition(db_conn, env["tenant_id"], env["work_request_id"], "preparing", "agent", "agent:document")

    # advance_to (not strict) stops where the guard fails, and never moves a file backwards
    assert state.advance_to(db_conn, env["tenant_id"], env["work_request_id"], "quality_check", "agent",
                            "agent:document") == "extracting"
    db_conn.execute("UPDATE documents SET status = 'read' WHERE id = %s;", (other,))
    assert state.advance_to(db_conn, env["tenant_id"], env["work_request_id"], "preparing", "agent",
                            "agent:document") == "preparing"
    assert state.advance_to(db_conn, env["tenant_id"], env["work_request_id"], "intake", "user",
                            str(env["user_id"]), "accountant") == "preparing"


def test_a_person_does_not_wait_for_the_optional_ai_help_but_does_wait_for_a_reading(db_conn, draft_env):
    """Seen on the stack: the accountant proposed by hand and asked for approval while the hosted AI still ran
    on the (already read) invoice; the request was refused for minutes."""
    env = draft_env
    t, w = env["tenant_id"], env["work_request_id"]
    doc = _read_document(db_conn, env)
    _submit(db_conn, env)
    job = "INSERT INTO jobs (tenant_id, work_request_id, step, subject_id) VALUES (%s, %s, %s, %s) RETURNING id;"
    reading = db_conn.execute(job, (t, w, "read_document", doc)).fetchone()[0]
    with pytest.raises(GuardFailed, match="pas encore lues"):
        state.transition(db_conn, t, w, "preparing", "user", str(env["user_id"]), "accountant")
    db_conn.execute("UPDATE jobs SET status = 'succeeded', finished_at = now() WHERE id = %s;", (reading,))
    db_conn.execute(job, (t, w, "ai_fill", doc))
    state.transition(db_conn, t, w, "preparing", "user", str(env["user_id"]), "accountant")
    assert _status(db_conn, w)[0] == "preparing"


def test_a_status_change_and_its_audit_row_roll_back_together(db_conn, draft_env):
    env = draft_env
    _read_document(db_conn, env)
    db_conn.commit()
    _submit(db_conn, env)
    db_conn.rollback()
    set_rls_context(db_conn, env["tenant_id"], env["user_id"])
    assert _status(db_conn, env["work_request_id"])[0] == "draft"
    assert state.history(db_conn, env["tenant_id"], env["work_request_id"]) == []


# ------------------------------------------------------------------------------------------- the agents move the file

def test_the_agent_chain_moves_the_file_to_quality_check(db_conn, draft_env):
    env = draft_env
    doc = _read_document(db_conn, env)
    _bank_statement(db_conn, env)
    _submit(db_conn, env)

    # As in the worker: the job is still 'running' while its handoff runs in the same transaction (seen on
    # the stack: the guard counted it as a reading in progress and the document agent could not hand off).
    read = _job(env, "read_document", doc, db_conn)
    db_conn.execute("UPDATE jobs SET status = 'running', locked_at = now(), finished_at = NULL WHERE id = %s;", (read.id,))
    orchestrator.after_step(db_conn, read)
    assert _status(db_conn, env["work_request_id"])[0] == "preparing"
    job = _job(env, "prepare_proposals", env["work_request_id"], db_conn)
    orchestrator.after_step(db_conn, job, orchestrator.prepare_proposals(db_conn, job))
    assert _status(db_conn, env["work_request_id"])[0] == "reconciling"
    job = _job(env, "reconcile", env["work_request_id"], db_conn)
    orchestrator.after_step(db_conn, job, orchestrator.reconcile(db_conn, job))

    assert _path(db_conn, env) == ["draft", "intake", "extracting", "preparing", "reconciling", "quality_check"]
    actors = [h["actor_id"] for h in state.history(db_conn, env["tenant_id"], env["work_request_id"])]
    assert actors[:2] == [str(env["user_id"])] * 2 and actors[2:] == [
        "agent:document", "agent:bookkeeping", "agent:reconciliation"]


def test_a_blocking_issue_sends_the_file_to_needs_attention(db_conn, draft_env):
    env = draft_env
    doc = _read_document(db_conn, env)
    db_conn.execute(
        "INSERT INTO issues (tenant_id, client_entity_id, work_request_id, subject_document_id, code, severity, "
        "status, evidence_refs) VALUES (%s, %s, %s, %s, 'TOTALS_INCONSISTENT', 'blocking', 'open', '[]');",
        (env["tenant_id"], env["client_id"], env["work_request_id"], doc),
    )
    _submit(db_conn, env)
    orchestrator.after_step(db_conn, _job(env, "read_document", doc, db_conn))
    job = _job(env, "prepare_proposals", env["work_request_id"], db_conn)
    orchestrator.after_step(db_conn, job, orchestrator.prepare_proposals(db_conn, job))
    assert _path(db_conn, env)[-2:] == ["quality_check", "needs_attention"]
    assert state.history(db_conn, env["tenant_id"], env["work_request_id"])[-1]["actor_id"] == "agent:orchestrator"


def test_agents_never_submit_a_file_a_client_uploaded(db_conn, draft_env):
    env = draft_env
    doc = _read_document(db_conn, env)  # nobody from the firm submitted the file
    orchestrator.after_step(db_conn, _job(env, "read_document", doc, db_conn))
    assert _status(db_conn, env["work_request_id"])[0] == "draft"


# ------------------------------------------------------------------------------------------- approval

def _proposal(conn: psycopg.Connection, env: dict) -> None:
    prop_id = uuid.uuid4()
    t, c = env["tenant_id"], env["client_id"]
    conn.execute(
        "INSERT INTO journal_proposals (id, tenant_id, client_entity_id, work_request_id, revision, journal_code, "
        "entry_date, label, proposed_by, status) VALUES (%s, %s, %s, %s, 1, 'ACH', '2026-10-10', 'Achat', "
        "'rules', 'proposed');",
        (prop_id, t, c, env["work_request_id"]),
    )
    conn.execute(
        "INSERT INTO journal_lines (id, tenant_id, client_entity_id, journal_proposal_id, line_no, account_id, "
        "account_code, label, currency, debit_tx, credit_tx, debit_mad, credit_mad) VALUES "
        "(%s, %s, %s, %s, 1, %s, '6111000', 'Achats', 'MAD', 500, 0, 500, 0), "
        "(%s, %s, %s, %s, 2, %s, '4411000', 'Fournisseur', 'MAD', 0, 500, 0, 500);",
        (uuid.uuid4(), t, c, prop_id, env["acc_6111"], uuid.uuid4(), t, c, prop_id, env["acc_4411"]),
    )


def test_a_rejected_file_goes_back_to_preparation_as_a_new_revision(db_conn, approval_test_env):  # noqa: F811
    env = approval_test_env
    t, c, w = env["tenant_id"], env["client_id"], env["work_request_id"]
    set_rls_context(db_conn, t, env["preparer_id"])
    _proposal(db_conn, env)
    req = request_work_request_approval(db_conn, t, c, w, env["preparer_id"])
    assert _status(db_conn, w) == ("awaiting_approval", 1)

    set_rls_context(db_conn, t, env["decider_oec_id"])
    decide_work_request_approval(db_conn, t, uuid.UUID(req["id"]), env["decider_oec_id"], "rejected",
                                 "Pièce manquante pour l'achat")
    assert _status(db_conn, w) == ("preparing", 2)
    last = state.history(db_conn, t, w)[-1]
    assert (last["from_status"], last["to_status"], last["reason"]) == (
        "awaiting_approval", "preparing", "Pièce manquante pour l'achat")

    set_rls_context(db_conn, t, env["preparer_id"])
    request_work_request_approval(db_conn, t, c, w, env["preparer_id"])  # walks the file forward again
    assert _status(db_conn, w) == ("awaiting_approval", 2)
    hist = state.history(db_conn, t, w)
    assert [h["to_status"] for h in hist] == [
        "extracting", "preparing", "reconciling", "quality_check", "awaiting_approval",
        "preparing", "reconciling", "quality_check", "awaiting_approval",
    ]
