"""Cancelling a monthly file (ARCHITECTURE.md D.1, docs/plans/phase-8d-cancel.md).

The file moves to `cancelled` through `transition()`, with the reason in its history. In the same transaction a
pending approval is cancelled and the file's queued jobs end as `cancelled`. Documents, readings, proposals,
issues and the audit trail are kept: evidence is never deleted.
"""

from __future__ import annotations

import uuid

import psycopg

from avenel.workflow import state

# Firm owner and manager: B.2 gives the manager "assign work, manage clients and periods".
CANCEL_ROLES = frozenset({"owner", "manager"})
CLOSED = frozenset({"cancelled", "failed"})


class CancelNotAllowed(state.WorkflowError):
    """The caller's role may not cancel a file."""


def cancel(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    work_request_id: uuid.UUID,
    actor_id: str,
    actor_role: str,
    reason: str,
) -> str:
    """Cancels the file. Returns its previous status. Call in the caller's transaction."""
    if actor_role not in CANCEL_ROLES:
        raise CancelNotAllowed("Seuls le responsable et le gérant du cabinet peuvent annuler un dossier.")
    reason = reason.strip()
    if not reason:
        raise state.GuardFailed("Indiquez le motif de l'annulation.")
    previous = state.transition(conn, tenant_id, work_request_id, "cancelled", "user", actor_id, actor_role,
                                reason=reason)
    # A pending approval is closed as a decision: who, when and why (001 check). Separation of duties (001
    # check) also covers it: the person who prepared the file cannot close its approval.
    pending = conn.execute(
        "SELECT prepared_by, single_person_policy FROM approvals "
        "WHERE tenant_id = %s AND work_request_id = %s AND status = 'pending';",
        (tenant_id, work_request_id),
    ).fetchall()
    if any(str(p) == actor_id and not single for p, single in pending):
        raise state.GuardFailed("Vous avez préparé ce dossier : un autre responsable du cabinet doit l'annuler.")
    conn.execute(
        "UPDATE approvals SET status = 'cancelled', decided_by = %s, decided_at = now(), reason = %s "
        "WHERE tenant_id = %s AND work_request_id = %s AND status = 'pending';",
        (actor_id, f"Dossier annulé : {reason}", tenant_id, work_request_id),
    )
    conn.execute(
        "UPDATE jobs SET status = 'cancelled', finished_at = now(), last_error = 'dossier annulé' "
        "WHERE tenant_id = %s AND work_request_id = %s AND status = 'queued';",
        (tenant_id, work_request_id),
    )
    return previous


def is_closed(conn: psycopg.Connection, tenant_id: uuid.UUID, work_request_id: uuid.UUID, lock: bool = False) -> bool:
    """True when the file is cancelled or failed: nothing more is done on it."""
    return state.current_status(conn, tenant_id, work_request_id, lock=lock) in CLOSED
