"""Lettrage API routes (Phase 6b, ARCHITECTURE.md D.7b).

Lettrage is internal firm work: client users have no access, operators may read only.
Every mutating route commits before responding (Phase 4 finding).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from apps.api.deps import get_current_session, get_db
from avenel.clients.service import get_client_entity
from avenel.lettrage.service import (
    LettrageError,
    LettrageNotFound,
    accept_group,
    create_manual_group,
    generate_candidates,
    get_group,
    group_client,
    list_groups,
    list_open_items,
    reject_group,
    reverse_group,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Lettrage"])

_NOT_FOUND = "Entreprise cliente introuvable."
_FORBIDDEN = "Action non autorisée pour ce rôle."


def _require_client(conn: psycopg.Connection, session: UserSession, client_id: uuid.UUID, write: bool) -> None:
    if session.role == "client_user":
        # Out-of-scope stays 404 (no existence leak); in scope, the action is still refused.
        if client_id not in session.client_scope_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_FORBIDDEN)
    if get_client_entity(conn, session.tenant_id, client_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    if write and session.role == "operator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_FORBIDDEN)


def _group_or_404(conn: psycopg.Connection, session: UserSession, group_id: uuid.UUID) -> uuid.UUID:
    try:
        client_id = group_client(conn, session.tenant_id, group_id)
    except LettrageNotFound as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    _require_client(conn, session, client_id, write=True)
    return client_id


@router.get("/clients/{client_id}/open-items", operation_id="listOpenItems")
def open_items_endpoint(
    client_id: uuid.UUID,
    account_class: Literal["customer", "supplier"],
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    as_of: datetime.date | None = None,
    include_settled: bool = False,
) -> dict[str, Any]:
    """Open customer (342x) or supplier (441x) items of approved proposals, with balances per counterparty."""
    _require_client(conn, session, client_id, write=False)
    return list_open_items(conn, session.tenant_id, client_id, account_class, as_of, include_settled)


@router.get("/clients/{client_id}/lettrage-groups", operation_id="listLettrageGroups")
def list_groups_endpoint(
    client_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    status_filter: Annotated[
        Literal["proposed", "accepted", "rejected", "superseded", "reversed"] | None, Query(alias="status")
    ] = None,
) -> list[dict[str, Any]]:
    _require_client(conn, session, client_id, write=False)
    return list_groups(conn, session.tenant_id, client_id, status_filter)


@router.post("/clients/{client_id}/lettrage-groups:generate", operation_id="generateLettrageCandidates")
def generate_endpoint(
    client_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> list[dict[str, Any]]:
    _require_client(conn, session, client_id, write=True)
    res = generate_candidates(conn, session.tenant_id, client_id, str(session.user_id))
    conn.commit()
    return res


class AllocationInput(BaseModel):
    journal_line_id: uuid.UUID
    amount_mad: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class ManualGroupInput(BaseModel):
    allocations: list[AllocationInput] = Field(min_length=2, max_length=50)


@router.post("/clients/{client_id}/lettrage-groups", status_code=201, operation_id="createManualLettrageGroup")
def manual_endpoint(
    client_id: uuid.UUID,
    payload: ManualGroupInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    _require_client(conn, session, client_id, write=True)
    try:
        res = create_manual_group(conn, session.tenant_id, client_id, str(session.user_id),
                                  [(a.journal_line_id, a.amount_mad) for a in payload.allocations])
    except LettrageError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    conn.commit()
    return res


@router.get("/lettrage-groups/{group_id}", operation_id="getLettrageGroup")
def get_endpoint(
    group_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    try:
        client_id = group_client(conn, session.tenant_id, group_id)
    except LettrageNotFound as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    _require_client(conn, session, client_id, write=False)
    return get_group(conn, session.tenant_id, group_id)


def _decide(conn: psycopg.Connection, fn, *args) -> dict[str, Any]:
    try:
        res = fn(conn, *args)
    except LettrageError as err:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    conn.commit()
    return res


@router.post("/lettrage-groups/{group_id}:accept", operation_id="acceptLettrageGroup")
def accept_endpoint(
    group_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    _group_or_404(conn, session, group_id)
    return _decide(conn, accept_group, session.tenant_id, group_id, session.user_id)


@router.post("/lettrage-groups/{group_id}:reject", operation_id="rejectLettrageGroup")
def reject_endpoint(
    group_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    _group_or_404(conn, session, group_id)
    return _decide(conn, reject_group, session.tenant_id, group_id, session.user_id)


class ReverseInput(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/lettrage-groups/{group_id}:reverse", operation_id="reverseLettrageGroup")
def reverse_endpoint(
    group_id: uuid.UUID,
    payload: ReverseInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    _group_or_404(conn, session, group_id)
    return _decide(conn, reverse_group, session.tenant_id, group_id, session.user_id, payload.reason)
