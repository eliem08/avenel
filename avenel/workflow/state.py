"""Work request state machine (ARCHITECTURE.md D.1, docs/plans/phase-8c-workflow.md).

`work_requests.status` changes only through `transition()`: it locks the row, refuses an edge outside the
D.1 graph, checks the edge's guard, writes the status and an audit event, all in the caller's transaction.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg

# The straight part of the graph, walked one edge at a time by advance_to().
FORWARD_PATH = ("draft", "intake", "extracting", "preparing", "reconciling", "quality_check")
TERMINAL = frozenset({"completed", "completed_with_open_items", "cancelled", "failed"})
ALL_STATES = frozenset(
    FORWARD_PATH
    + ("needs_attention", "awaiting_approval", "exporting")
    + tuple(TERMINAL)
)

EDGES: dict[str, frozenset[str]] = {
    "draft": frozenset({"intake"}),
    "intake": frozenset({"extracting"}),
    "extracting": frozenset({"preparing"}),
    "preparing": frozenset({"reconciling"}),
    "reconciling": frozenset({"quality_check"}),
    "quality_check": frozenset({"needs_attention", "awaiting_approval"}),
    "needs_attention": frozenset({"awaiting_approval"}),
    "awaiting_approval": frozenset({"exporting", "preparing"}),
    "exporting": frozenset({"completed", "completed_with_open_items"}),
}

# Roles holding `work.submit` (D.1 guard on draft -> intake). Firm staff only.
SUBMIT_ROLES = frozenset({"owner", "manager", "accountant", "staff"})


class WorkflowError(Exception):
    """A status change was refused. The message is French, for the screen (the API answers 409)."""


class TransitionNotAllowed(WorkflowError):
    """The edge is not in the D.1 graph."""


class GuardFailed(WorkflowError):
    """The edge exists but its guard is not met."""


def allowed(frm: str, to: str) -> bool:
    if to == "failed":
        return True
    if to == "cancelled":
        return frm not in TERMINAL
    return to in EDGES.get(frm, frozenset())


def _blocking_issues(conn: psycopg.Connection, tenant_id: uuid.UUID, wr: uuid.UUID) -> int:
    row = conn.execute(
        "SELECT count(*) FROM issues WHERE tenant_id = %s AND work_request_id = %s "
        "AND severity = 'blocking' AND status NOT IN ('resolved', 'waived');",
        (tenant_id, wr),
    ).fetchone()
    return int(row[0]) if row else 0


def _check_guard(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    wr: uuid.UUID,
    frm: str,
    to: str,
    actor_type: str,
    actor_role: str | None,
    finishing_job_id: uuid.UUID | None = None,
) -> None:
    if (frm, to) == ("draft", "intake"):
        if actor_type != "user" or actor_role not in SUBMIT_ROLES:
            raise GuardFailed("Seul un membre du cabinet peut soumettre le dossier.")
        row = conn.execute(
            """
            SELECT p.status,
                   EXISTS (SELECT 1 FROM documents d WHERE d.tenant_id = w.tenant_id AND d.work_request_id = w.id
                             AND d.status <> 'quarantined'),
                   EXISTS (SELECT 1 FROM bank_statements b WHERE b.tenant_id = w.tenant_id
                             AND b.client_entity_id = w.client_entity_id
                             AND b.period_start <= p.ends_on AND b.period_end >= p.starts_on)
            FROM work_requests w
            JOIN accounting_periods p ON p.tenant_id = w.tenant_id AND p.id = w.accounting_period_id
            WHERE w.tenant_id = %s AND w.id = %s;
            """,
            (tenant_id, wr),
        ).fetchone()
        if row is None:
            raise LookupError("dossier introuvable")
        if row[0] != "open":
            raise GuardFailed("La période comptable n'est pas ouverte.")
        if not (row[1] or row[2]):
            raise GuardFailed("Aucune pièce ni relevé bancaire n'est joint au dossier.")
    elif (frm, to) == ("extracting", "preparing"):
        # D.1: "every document read, needs_review or rejected; none processing". Bank statements are parsed at
        # upload and never read (they stay 'received'), and an upload never completed stays 'received' with no
        # job: neither is waited for, as in the orchestrator's handoff (phase 8a). The optional AI help
        # ('ai_fill') is not waited for either: the document is already read, and a person who reviewed it may
        # go on (the agents still wait for it before proposing). The job that is finishing right now, in this
        # transaction, does not count.
        row = conn.execute(
            """
            SELECT count(*) FROM documents d
            WHERE d.tenant_id = %(t)s AND d.work_request_id = %(w)s
              AND (d.status = 'processing'
                   OR EXISTS (SELECT 1 FROM jobs j WHERE j.tenant_id = d.tenant_id AND j.subject_id = d.id
                                AND j.step = 'read_document' AND j.status IN ('queued', 'running')
                                AND j.id IS DISTINCT FROM %(j)s));
            """,
            {"t": tenant_id, "w": wr, "j": finishing_job_id},
        ).fetchone()
        if row and row[0]:
            raise GuardFailed(f"{row[0]} pièce(s) ne sont pas encore lues.")
    elif to == "awaiting_approval":
        n = _blocking_issues(conn, tenant_id, wr)
        if n:
            raise GuardFailed(f"{n} anomalie(s) bloquante(s) restent ouvertes.")


def current_status(conn: psycopg.Connection, tenant_id: uuid.UUID, wr: uuid.UUID, lock: bool = False) -> str:
    row = conn.execute(
        "SELECT status FROM work_requests WHERE tenant_id = %s AND id = %s" + (" FOR UPDATE;" if lock else ";"),
        (tenant_id, wr),
    ).fetchone()
    if row is None:
        raise LookupError("dossier introuvable")
    return str(row[0])


def transition(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    to: str,
    actor_type: str,
    actor_id: str | None,
    actor_role: str | None = None,
    reason: str | None = None,
    finishing_job_id: uuid.UUID | None = None,
) -> str:
    """Moves the work request to `to`. Returns the previous status. Call in the caller's transaction.

    `finishing_job_id`: the worker job whose step just succeeded (still 'running' until the transaction
    commits); a guard that waits for jobs does not wait for it.
    """
    if to not in ALL_STATES:
        raise TransitionNotAllowed(f"Statut de dossier inconnu : {to}.")
    frm = current_status(conn, tenant_id, work_request_id, lock=True)
    if not allowed(frm, to):
        raise TransitionNotAllowed(f"Le dossier ne peut pas passer du statut « {frm} » au statut « {to} ».")
    _check_guard(conn, tenant_id, work_request_id, frm, to, actor_type, actor_role, finishing_job_id)
    conn.execute(
        """
        UPDATE work_requests
        SET status = %(to)s, updated_at = now(),
            submitted_at = CASE WHEN %(to)s = 'intake' THEN COALESCE(submitted_at, now()) ELSE submitted_at END,
            completed_at = CASE WHEN %(to)s IN ('completed', 'completed_with_open_items') THEN now()
                                ELSE completed_at END,
            current_revision = CASE WHEN %(frm)s = 'awaiting_approval' AND %(to)s = 'preparing'
                                    THEN current_revision + 1 ELSE current_revision END
        WHERE tenant_id = %(t)s AND id = %(w)s;
        """,
        {"to": to, "frm": frm, "t": tenant_id, "w": work_request_id},
    )
    data: dict[str, Any] = {"from": frm, "to": to}
    if reason:
        data["reason"] = reason
    conn.execute(
        """
        INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
        VALUES (%s, %s, %s, 'work_request.status_changed', 'work_request', %s, %s::jsonb);
        """,
        (tenant_id, actor_type, actor_id, str(work_request_id), json.dumps(data)),
    )
    return frm


def advance_to(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    target: str,
    actor_type: str,
    actor_id: str | None,
    actor_role: str | None = None,
    strict: bool = False,
    finishing_job_id: uuid.UUID | None = None,
) -> str:
    """Walks FORWARD_PATH up to `target`, one guarded edge at a time. Never moves a file backwards.

    Stops at the first guard that fails: raises GuardFailed when `strict`, else leaves the file where it got
    to. Returns the status reached (unchanged when the file is already at or past `target`, or off the path).
    """
    if target not in FORWARD_PATH:
        raise ValueError(f"{target} n'est pas sur le chemin principal")
    status = current_status(conn, tenant_id, work_request_id, lock=True)
    if status not in FORWARD_PATH:
        return status
    while FORWARD_PATH.index(status) < FORWARD_PATH.index(target):
        nxt = FORWARD_PATH[FORWARD_PATH.index(status) + 1]
        try:
            transition(conn, tenant_id, work_request_id, nxt, actor_type, actor_id, actor_role,
                       finishing_job_id=finishing_job_id)
        except GuardFailed:
            if strict:
                raise
            return status
        status = nxt
    return status


def history(conn: psycopg.Connection, tenant_id: uuid.UUID, work_request_id: uuid.UUID) -> list[dict[str, Any]]:
    """Status changes of a work request, oldest first, from the audit trail."""
    rows = conn.execute(
        """
        SELECT data->>'from', data->>'to', data->>'reason', actor_type, actor_id, occurred_at
        FROM audit_events
        WHERE tenant_id = %s AND resource_type = 'work_request' AND resource_id = %s
          AND action = 'work_request.status_changed'
        ORDER BY id;
        """,
        (tenant_id, str(work_request_id)),
    ).fetchall()
    return [
        {"from_status": r[0], "to_status": r[1], "reason": r[2], "actor_type": r[3], "actor_id": r[4],
         "occurred_at": r[5].isoformat()}
        for r in rows
    ]
