"""Phase 8a: the orchestrator hands a work request from agent to agent, and each agent stays in its lane.

Real PostgreSQL, real proposal and reconciliation services. No provider and no OCR: documents are seeded
already read, as in the reconciliation tests.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

from avenel.bank.service import ingest_bank_statement
from avenel.jobs.queue import Job
from avenel.tenancy.auth import set_rls_context
from avenel.workforce import orchestrator
from avenel.workforce.agents import (
    AGENTS,
    FORBIDDEN_ACTIONS,
    AgentPermissionError,
    require,
)
from tests.reconciliation.test_reconciliation import recon_test_env  # noqa: F401 - fixture

INVOICE = {
    "invoice_number": {"value": "FA-2026-801"},
    "invoice_date": {"value": "2026-03-10"},
    "supplier_name": {"value": "Atlas Fournitures SARL"},
    "supplier_ice": {"value": "001234567890123"},
    "total_ht": {"value": 10000.00},
    "total_vat": {"value": 2000.00},
    "total_ttc": {"value": 12000.00},
}


def _read_document(conn: psycopg.Connection, env: dict, fields: dict = INVOICE, status: str = "read") -> uuid.UUID:
    """A purchase invoice already read (document, version, extraction), with no proposal yet."""
    import json

    doc_id, ver_id = uuid.uuid4(), uuid.uuid4()
    t, c, w = env["tenant_id"], env["client_id"], env["work_request_id"]
    conn.execute(
        "INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, status, "
        "original_filename, source_channel) VALUES (%s, %s, %s, %s, 'purchase_invoice', %s, 'f.pdf', 'console');",
        (doc_id, t, c, w, status),
    )
    conn.execute(
        "INSERT INTO document_versions (id, tenant_id, client_entity_id, document_id, version_number, object_key, "
        "sha256, mime_type, byte_size, page_count) VALUES (%s, %s, %s, %s, 1, 'k', %s, 'application/pdf', 1, 1);",
        (ver_id, t, c, doc_id, (uuid.uuid4().hex * 2)[:64]),
    )
    conn.execute(
        "INSERT INTO extractions (id, tenant_id, document_version_id, schema_version, engine, engine_version, "
        "status, fields, validation) VALUES (%s, %s, %s, '1.0', 'paddleocr', '2.7', 'succeeded', %s::jsonb, '{}');",
        (uuid.uuid4(), t, ver_id, json.dumps(fields)),
    )
    return doc_id


def _job(env: dict, step: str, subject: uuid.UUID, conn: psycopg.Connection) -> Job:
    """A real job row, already finished, so the step can be called directly and not picked by a worker."""
    row = conn.execute(
        "INSERT INTO jobs (tenant_id, work_request_id, step, subject_id, revision, status, finished_at) "
        "SELECT %(t)s, %(w)s, %(s)s, %(d)s, 1 + COALESCE(max(revision), 0), 'succeeded', now() FROM jobs "
        "WHERE tenant_id = %(t)s AND work_request_id = %(w)s AND step = %(s)s AND subject_id = %(d)s RETURNING id;",
        {"t": env["tenant_id"], "w": env["work_request_id"], "s": step, "d": subject},
    ).fetchone()
    return Job(row[0], env["tenant_id"], env["work_request_id"], step, subject, 1)


def _tasks(conn: psycopg.Connection, env: dict) -> list[tuple]:
    return conn.execute(
        "SELECT agent, step, outcome, handed_off_to FROM agent_tasks WHERE work_request_id = %s ORDER BY created_at;",
        (env["work_request_id"],),
    ).fetchall()


def _queued(conn: psycopg.Connection, env: dict) -> list[str]:
    rows = conn.execute(
        "SELECT step FROM jobs WHERE work_request_id = %s AND status = 'queued' ORDER BY created_at;",
        (env["work_request_id"],),
    ).fetchall()
    return [r[0] for r in rows]


def _bank_statement(conn: psycopg.Connection, env: dict) -> None:
    doc_id = uuid.uuid4()
    conn.execute(
        "INSERT INTO documents (id, tenant_id, client_entity_id, work_request_id, doc_type, original_filename, "
        "source_channel, status) VALUES (%s, %s, %s, %s, 'bank_statement', 'releve.csv', 'console', 'received');",
        (doc_id, env["tenant_id"], env["client_id"], env["work_request_id"]),
    )
    ingest_bank_statement(
        conn=conn, tenant_id=env["tenant_id"], client_entity_id=env["client_id"],
        bank_account_id=env["bank_account_id"], document_id=doc_id,
        file_bytes=b"# Solde initial: 100000.00\n# Solde final: 88000.00\nDate,Libelle,Debit,Credit\n"
                   b"2026-03-15,VIR ATLAS FOURNITURES FA-2026-801,12000.00,0.00\n",
        filename="releve.csv", work_request_id=env["work_request_id"], actor_id=str(env["user_id"]),
    )


# ------------------------------------------------------------------------------------------- permissions

def test_no_agent_may_approve_export_post_pay_or_send():
    for agent in AGENTS.values():
        assert not {a.rsplit(".", 1)[-1] for a in agent.actions} & FORBIDDEN_ACTIONS
        for verb in FORBIDDEN_ACTIONS:
            with pytest.raises(AgentPermissionError):
                require(agent, f"work_request.{verb}")


def test_an_agent_cannot_use_another_agents_action():
    with pytest.raises(AgentPermissionError):
        require(AGENTS["document"], "proposal.draft")
    with pytest.raises(AgentPermissionError):
        require(AGENTS["bookkeeping"], "reconciliation.propose")
    require(AGENTS["bookkeeping"], "proposal.draft")  # its own action is allowed


# ------------------------------------------------------------------------------------------- handoffs

def test_last_document_read_hands_off_to_bookkeeping_only_when_nothing_else_is_being_read(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env
    first = _read_document(db_conn, env)
    _read_document(db_conn, env, {**INVOICE, "invoice_number": {"value": "FA-2026-802"}}, status="processing")

    orchestrator.after_step(db_conn, _job(env, "read_document", first, db_conn))
    assert _queued(db_conn, env) == []  # another document is still being read
    assert _tasks(db_conn, env) == [("document", "read_document", "done", None)]

    db_conn.execute("UPDATE documents SET status = 'read' WHERE work_request_id = %s;", (env["work_request_id"],))
    orchestrator.after_step(db_conn, _job(env, "read_document", first, db_conn))
    assert _queued(db_conn, env) == ["prepare_proposals"]
    assert _tasks(db_conn, env)[-1] == ("document", "read_document", "handed_off", "bookkeeping")


def test_an_upload_never_completed_does_not_stall_the_file(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env
    doc = _read_document(db_conn, env)
    _read_document(db_conn, env, {**INVOICE, "invoice_number": {"value": "FA-2026-803"}}, status="received")
    orchestrator.after_step(db_conn, _job(env, "read_document", doc, db_conn))
    assert _queued(db_conn, env) == ["prepare_proposals"]


def test_full_chain_read_to_proposal_to_reconciliation_ready_for_review(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env
    doc = _read_document(db_conn, env)
    _bank_statement(db_conn, env)

    orchestrator.after_step(db_conn, _job(env, "read_document", doc, db_conn))
    job = _job(env, "prepare_proposals", env["work_request_id"], db_conn)
    summary = orchestrator.prepare_proposals(db_conn, job)
    assert summary == {"documents": 1, "proposed": 1, "blocked": 0}
    orchestrator.after_step(db_conn, job, summary)
    assert _queued(db_conn, env)[-1] == "reconcile"

    job = _job(env, "reconcile", env["work_request_id"], db_conn)
    summary = orchestrator.reconcile(db_conn, job)
    assert summary["matches"] >= 1
    orchestrator.after_step(db_conn, job, summary)

    proposals = db_conn.execute(
        "SELECT status, proposed_by FROM journal_proposals WHERE source_document_id = %s;", (doc,)
    ).fetchall()
    assert [p[0] for p in proposals] == ["proposed"]  # proposed only: never approved by an agent
    matches = db_conn.execute(
        "SELECT status FROM reconciliation_matches WHERE work_request_id = %s;", (env["work_request_id"],)
    ).fetchall()
    assert matches and {m[0] for m in matches} == {"proposed"}
    assert _tasks(db_conn, env)[-3:] == [
        ("bookkeeping", "prepare_proposals", "handed_off", "reconciliation"),
        ("reconciliation", "reconcile", "done", "human"),
        ("orchestrator", "finish", "ready_for_review", "human"),
    ]
    actors = db_conn.execute(
        "SELECT DISTINCT actor_id FROM audit_events WHERE actor_type = 'agent' AND resource_id = %s;",
        (str(env["work_request_id"]),),
    ).fetchall()
    assert {a[0] for a in actors} >= {"agent:document", "agent:bookkeeping", "agent:reconciliation"}


def test_running_an_agent_twice_does_not_duplicate_its_work(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env
    _read_document(db_conn, env)
    _bank_statement(db_conn, env)
    prep = _job(env, "prepare_proposals", env["work_request_id"], db_conn)
    assert orchestrator.prepare_proposals(db_conn, prep)["proposed"] == 1
    assert orchestrator.prepare_proposals(db_conn, prep) == {"documents": 0, "proposed": 0, "blocked": 0}

    rec = _job(env, "reconcile", env["work_request_id"], db_conn)
    first = orchestrator.reconcile(db_conn, rec)["matches"]
    again = orchestrator.reconcile(db_conn, rec)
    assert again["matches"] == 0 and again["already_proposed"] == first


def test_without_bank_lines_and_with_a_blocking_issue_the_file_is_escalated_to_a_person(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env
    doc = _read_document(db_conn, env)
    db_conn.execute(
        "INSERT INTO issues (tenant_id, client_entity_id, work_request_id, subject_document_id, code, severity, "
        "status, evidence_refs) VALUES (%s, %s, %s, %s, 'TOTALS_INCONSISTENT', 'blocking', 'open', '[]');",
        (env["tenant_id"], env["client_id"], env["work_request_id"], doc),
    )
    job = _job(env, "prepare_proposals", env["work_request_id"], db_conn)
    summary = orchestrator.prepare_proposals(db_conn, job)
    assert summary["documents"] == 0  # a document with a blocking issue waits for a person, no proposal
    orchestrator.after_step(db_conn, job, summary)
    assert _queued(db_conn, env) == []
    assert _tasks(db_conn, env)[-2:] == [
        ("bookkeeping", "prepare_proposals", "done", "human"),
        ("orchestrator", "finish", "escalated", "human"),
    ]


# ------------------------------------------------------------------------------------------- the record

def test_agent_tasks_are_append_only_and_tenant_scoped(db_conn, app_conn, recon_test_env):  # noqa: F811
    env = recon_test_env
    orchestrator.record_task(db_conn, None, env["tenant_id"], env["work_request_id"], "orchestrator", "finish",
                             "ready_for_review", "human")
    db_conn.commit()

    other = uuid.uuid4()
    set_rls_context(app_conn, other)
    assert app_conn.execute("SELECT count(*) FROM agent_tasks;").fetchone() == (0,)
    app_conn.rollback()

    set_rls_context(app_conn, env["tenant_id"])
    assert app_conn.execute(
        "SELECT count(*) FROM agent_tasks WHERE work_request_id = %s;", (env["work_request_id"],)
    ).fetchone() == (1,)
    for sql in ("UPDATE agent_tasks SET outcome = 'escalated';", "DELETE FROM agent_tasks;"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app_conn.execute(sql)
        app_conn.rollback()
        set_rls_context(app_conn, env["tenant_id"])
