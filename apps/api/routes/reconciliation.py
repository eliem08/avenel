"""Bank reconciliation API routes (Phase 4)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.reconciliation.service import (
    accept_reconciliation_match,
    generate_reconciliation_matches,
    list_reconciliation_matches,
    reject_reconciliation_match,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1/reconciliation", tags=["Reconciliation"])


class GenerateMatchesInput(BaseModel):
    client_entity_id: uuid.UUID
    work_request_id: uuid.UUID
    date_window_days: int | None = None


def _check_client_scope(session: UserSession, client_id: uuid.UUID) -> None:
    if session.role == "client_user" and client_id not in session.client_scope_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")


def _resolve_work_request(
    conn: psycopg.Connection,
    session: UserSession,
    work_request_id: uuid.UUID,
) -> uuid.UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT client_entity_id FROM work_requests
            WHERE tenant_id = %s AND id = %s
            LIMIT 1;
            """,
            (session.tenant_id, work_request_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande de travail introuvable.")
        client_id = uuid.UUID(str(row[0]))
        _check_client_scope(session, client_id)
        return client_id


@router.get("/matches")
def list_matches_endpoint(
    work_request_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Lists reconciliation candidates and accepted matches for a work request."""
    _resolve_work_request(conn, session, work_request_id)
    return list_reconciliation_matches(conn, session.tenant_id, work_request_id)


@router.get("/bank-transactions", operation_id="listWorkRequestBankTransactions")
def list_bank_transactions_endpoint(
    work_request_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Statements attached to a monthly file and their lines (Phase 4 completion: no endpoint
    returned bank lines, so the reconciliation screen could not show them)."""
    client_id = _resolve_work_request(conn, session, work_request_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bs.id, bs.period_start, bs.period_end, bs.opening_balance, bs.closing_balance,
                   bs.balance_check, d.original_filename
            FROM bank_statements bs
            JOIN documents d ON d.id = bs.document_id AND d.tenant_id = bs.tenant_id
            WHERE bs.tenant_id = %s AND bs.client_entity_id = %s AND d.work_request_id = %s
            ORDER BY bs.period_start;
            """,
            (session.tenant_id, client_id, work_request_id),
        )
        statements = [
            {
                "id": str(r[0]), "period_start": r[1].isoformat(), "period_end": r[2].isoformat(),
                "opening_balance": float(r[3]), "closing_balance": float(r[4]),
                "balance_check": r[5], "filename": r[6],
            }
            for r in cur.fetchall()
        ]
        cur.execute(
            """
            SELECT bt.id, bt.bank_statement_id, bt.line_index, bt.booking_date, bt.value_date,
                   bt.amount, bt.currency, bt.description, bt.external_reference
            FROM bank_transactions bt
            JOIN bank_statements bs ON bs.id = bt.bank_statement_id AND bs.tenant_id = bt.tenant_id
            JOIN documents d ON d.id = bs.document_id AND d.tenant_id = bs.tenant_id
            WHERE bt.tenant_id = %s AND bt.client_entity_id = %s AND d.work_request_id = %s
            ORDER BY bt.booking_date, bt.line_index;
            """,
            (session.tenant_id, client_id, work_request_id),
        )
        items = [
            {
                "id": str(r[0]), "bank_statement_id": str(r[1]), "line_index": r[2],
                "booking_date": r[3].isoformat(), "value_date": r[4].isoformat() if r[4] else None,
                "amount": float(r[5]), "currency": r[6], "description": r[7], "external_reference": r[8],
            }
            for r in cur.fetchall()
        ]
    return {"statements": statements, "items": items}


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_matches_endpoint(
    payload: GenerateMatchesInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Triggers candidate generation for bank reconciliation."""
    # The company comes from the work request, never from the body alone (Phase 4: a body
    # client_entity_id that did not match the work request was accepted).
    wr_client = _resolve_work_request(conn, session, payload.work_request_id)
    if wr_client != payload.client_entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande de travail introuvable.")

    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    res = generate_reconciliation_matches(
        conn=conn,
        tenant_id=session.tenant_id,
        client_entity_id=payload.client_entity_id,
        work_request_id=payload.work_request_id,
        date_window_days=payload.date_window_days,
    )
    # Commit before responding: the connection's own commit runs at dependency teardown,
    # which can happen after the client has already re-read (Phase 4 finding).
    conn.commit()
    return res


@router.post("/matches/{match_id}/accept")
def accept_match_endpoint(
    match_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Accepts a reconciliation match. Enforces double-match prevention."""
    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    try:
        res = accept_reconciliation_match(
            conn=conn,
            tenant_id=session.tenant_id,
            match_id=match_id,
            actor_id=str(session.user_id),
        )
        # Commit before responding: the connection's own commit runs at dependency teardown,
        # which can happen after the client has already re-read (Phase 4 finding).
        conn.commit()
        return res
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err


@router.post("/matches/{match_id}/reject")
def reject_match_endpoint(
    match_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Rejects a reconciliation match candidate."""
    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    try:
        res = reject_reconciliation_match(
            conn=conn,
            tenant_id=session.tenant_id,
            match_id=match_id,
            actor_id=str(session.user_id),
        )
        # Commit before responding: the connection's own commit runs at dependency teardown,
        # which can happen after the client has already re-read (Phase 4 finding).
        conn.commit()
        return res
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
