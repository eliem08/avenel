"""Orchestrator: hands a work request from one agent to the next through the job queue (Phase 8a).

Runs inside the worker, in the same transaction as the step that just succeeded, so a handoff commits
together with the work it follows. Nothing here approves or exports. The work request's status follows the
agents through the D.1 state machine (phase 8c): extracting -> preparing -> reconciling -> quality_check, and
needs_attention when blocking issues are open. The chain ends with the file "ready for review" for a person,
or "escalated".
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg

from avenel.jobs.queue import Job, enqueue
from avenel.proposals.service import (
    active_proposal_for_document,
    generate_and_save_proposal_for_document,
)
from avenel.reconciliation.service import generate_reconciliation_matches
from avenel.workflow import state as workflow
from avenel.workforce.agents import AGENT_FOR_STEP, AGENTS, require

# Document types the entry builder knows how to propose an entry for (entry_builder.py).
PROPOSABLE_DOC_TYPES = ("purchase_invoice", "sales_invoice", "credit_note", "receipt", "expense_note")


def record_task(
    conn: psycopg.Connection,
    job: Job | None,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    agent: str,
    step: str,
    outcome: str,
    handed_off_to: str | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    """Appends one agent task row and its audit event (actor_type 'agent')."""
    conn.execute(
        """
        INSERT INTO agent_tasks (tenant_id, work_request_id, agent, step, job_id, subject_id, outcome,
                                 handed_off_to, summary, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, clock_timestamp());
        """,
        (tenant_id, work_request_id, agent, step, job.id if job else None, job.subject_id if job else None,
         outcome, handed_off_to, json.dumps(summary or {})),
    )
    conn.execute(
        """
        INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
        VALUES (%s, 'agent', %s, %s, 'work_request', %s, %s::jsonb);
        """,
        (tenant_id, f"agent:{agent}", f"agent.{step}.{outcome}", str(work_request_id),
         json.dumps({"handed_off_to": handed_off_to, **(summary or {})})),
    )


def _client_of(conn: psycopg.Connection, tenant_id: uuid.UUID, work_request_id: uuid.UUID) -> uuid.UUID:
    row = conn.execute(
        "SELECT client_entity_id FROM work_requests WHERE tenant_id = %s AND id = %s;",
        (tenant_id, work_request_id),
    ).fetchone()
    if row is None:
        raise LookupError("demande de travail introuvable")
    return uuid.UUID(str(row[0]))


# ------------------------------------------------------------------------------------------- agent steps

def prepare_proposals(conn: psycopg.Connection, job: Job) -> dict[str, Any]:
    """Bookkeeping agent: proposes an entry for each read document that has none and no blocking issue."""
    require(AGENTS["bookkeeping"], "proposal.draft")
    client_id = _client_of(conn, job.tenant_id, job.work_request_id)
    docs = conn.execute(
        """
        SELECT d.id FROM documents d
        WHERE d.tenant_id = %(t)s AND d.work_request_id = %(w)s
          AND d.status IN ('read', 'needs_review') AND d.doc_type = ANY(%(types)s)
          AND NOT EXISTS (SELECT 1 FROM journal_proposals p
                          WHERE p.tenant_id = d.tenant_id AND p.source_document_id = d.id
                            AND p.status NOT IN ('superseded', 'rejected'))
          AND NOT EXISTS (SELECT 1 FROM issues i
                          WHERE i.tenant_id = d.tenant_id AND i.subject_document_id = d.id
                            AND i.severity = 'blocking' AND i.status NOT IN ('resolved', 'waived'))
        ORDER BY d.received_at, d.id;
        """,
        {"t": job.tenant_id, "w": job.work_request_id, "types": list(PROPOSABLE_DOC_TYPES)},
    ).fetchall()
    proposed, blocked = 0, 0
    for (doc_id,) in docs:
        if active_proposal_for_document(conn, job.tenant_id, doc_id) is not None:
            continue  # proposed by a person since the list was read
        result = generate_and_save_proposal_for_document(
            conn=conn, tenant_id=job.tenant_id, client_entity_id=client_id,
            work_request_id=job.work_request_id, document_id=doc_id, actor_id="agent:bookkeeping",
        )
        if result.get("status") == "blocked":
            blocked += 1
        else:
            proposed += 1
    return {"documents": len(docs), "proposed": proposed, "blocked": blocked}


def reconcile(conn: psycopg.Connection, job: Job) -> dict[str, Any]:
    """Reconciliation agent: proposes bank matches, unless proposals already wait for a person."""
    require(AGENTS["reconciliation"], "reconciliation.propose")
    client_id = _client_of(conn, job.tenant_id, job.work_request_id)
    existing = conn.execute(
        "SELECT count(*) FROM reconciliation_matches WHERE tenant_id = %s AND work_request_id = %s "
        "AND status = 'proposed';",
        (job.tenant_id, job.work_request_id),
    ).fetchone()
    if existing and existing[0]:
        return {"matches": 0, "already_proposed": int(existing[0])}
    matches = generate_reconciliation_matches(
        conn=conn, tenant_id=job.tenant_id, client_entity_id=client_id, work_request_id=job.work_request_id,
    )
    return {"matches": len(matches)}


# ------------------------------------------------------------------------------------------- handoffs

def _finish(conn: psycopg.Connection, job: Job, agent: str, summary: dict[str, Any]) -> None:
    row = conn.execute(
        """
        SELECT count(*) FROM issues WHERE tenant_id = %s AND work_request_id = %s
          AND severity = 'blocking' AND status NOT IN ('resolved', 'waived');
        """,
        (job.tenant_id, job.work_request_id),
    ).fetchone()
    n = int(row[0]) if row else 0
    t, w = job.tenant_id, job.work_request_id
    if workflow.advance_to(conn, t, w, "quality_check", "agent", f"agent:{agent}") == "quality_check" and n:
        workflow.transition(conn, t, w, "needs_attention", "agent", "agent:orchestrator",
                            reason=f"{n} anomalie(s) bloquante(s)")
    record_task(conn, job, job.tenant_id, job.work_request_id, agent, job.step, "done", "human", summary)
    record_task(conn, None, job.tenant_id, job.work_request_id, "orchestrator", "finish",
                "escalated" if n else "ready_for_review", "human", {"blocking_issues": n})


def after_step(conn: psycopg.Connection, job: Job, summary: dict[str, Any] | None = None) -> None:
    """Decides the next agent once `job` has succeeded. Call in the job's transaction."""
    if job.step not in AGENT_FOR_STEP:
        return
    agent = AGENT_FOR_STEP[job.step].name
    summary = summary or {}
    t, w = job.tenant_id, job.work_request_id

    if job.step in ("read_document", "ai_fill"):
        # Two workers (reading, AI) can finish jobs of the same file at the same moment; each would see the
        # other's job as still running and neither would hand off. This lock makes them take turns: the
        # second one sees the first one's job finished and hands off.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0));", (f"handoff:{w}",))
        # Wait only for documents actually being read or getting AI help (including this document's own
        # 'ai_fill' job, queued by its reading). An upload started but never completed stays 'received' with
        # no job; waiting for it would stall the file (seen on the stack, 17 Nov 2026).
        # Known limit: two workers finishing at the same instant could each wait for the other; the stack
        # runs one worker, one job at a time.
        pending = conn.execute(
            """
            SELECT count(*) FROM documents d
            WHERE d.tenant_id = %(t)s AND d.work_request_id = %(w)s
              AND ((d.status = 'processing' AND d.id <> %(d)s)
                   OR EXISTS (SELECT 1 FROM jobs j WHERE j.tenant_id = d.tenant_id AND j.subject_id = d.id
                                AND j.step IN ('read_document', 'ai_fill') AND j.id <> %(j)s
                                AND j.status IN ('queued', 'running')));
            """,
            {"t": t, "w": w, "d": job.subject_id, "j": job.id},
        ).fetchone()
        if pending and pending[0]:  # other documents still being read: the last one hands off
            record_task(conn, job, t, w, agent, job.step, "done", None, {"documents_pending": int(pending[0])})
            return
        enqueue(conn, t, w, "prepare_proposals", w)
        workflow.advance_to(conn, t, w, "preparing", "agent", f"agent:{agent}", finishing_job_id=job.id)
        record_task(conn, job, t, w, agent, job.step, "handed_off", "bookkeeping", summary)
        return

    if job.step == "prepare_proposals":
        has_bank = conn.execute(
            "SELECT 1 FROM bank_transactions WHERE tenant_id = %s AND client_entity_id = %s LIMIT 1;",
            (t, _client_of(conn, t, w)),
        ).fetchone()
        if has_bank:
            enqueue(conn, t, w, "reconcile", w)
            workflow.advance_to(conn, t, w, "reconciling", "agent", f"agent:{agent}")
            record_task(conn, job, t, w, agent, job.step, "handed_off", "reconciliation", summary)
            return

    _finish(conn, job, agent, summary)  # no further agent: a person takes over
