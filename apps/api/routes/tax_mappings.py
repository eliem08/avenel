"""Client tax mappings (Part K 15): which account receives each VAT code, per client company.

Phase 3 completion. Before, mappings could only be created by a test helper, so no real
document could ever become a proposal (every one ended in ACCOUNT_UNMAPPED).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.clients.service import get_client_entity
from avenel.proposals.tax_mapping import (
    TaxMappingError,
    list_client_tax_mappings,
    set_client_tax_mapping,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Tax mappings"])

WRITE_ROLES = ("owner", "manager", "accountant")


class TaxMappingInput(BaseModel):
    tax_code: str
    direction: str
    account_id: uuid.UUID


def _client_in_scope(conn: psycopg.Connection, session: UserSession, client_id: uuid.UUID) -> None:
    if session.role == "client_user" and client_id not in session.client_scope_ids:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")
    if not get_client_entity(conn, session.tenant_id, client_id):
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")


@router.get("/client-entities/{id}/tax-mappings", operation_id="listClientTaxMappings")
async def list_tax_mappings(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    _client_in_scope(conn, session, id)
    if session.role == "client_user":
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")
    return {
        "items": list_client_tax_mappings(conn, session.tenant_id, id),
        "can_approve": session.professional_registration_no is not None,
    }


@router.put("/client-entities/{id}/tax-mappings", operation_id="setClientTaxMapping")
async def put_tax_mapping(
    id: uuid.UUID,
    body: TaxMappingInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    _client_in_scope(conn, session, id)
    if session.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")
    try:
        res = set_client_tax_mapping(
            conn,
            session.tenant_id,
            id,
            body.tax_code,
            body.direction,
            body.account_id,
            actor_id=session.user_id,
            actor_is_registered_professional=session.professional_registration_no is not None,
        )
        conn.commit()
        return res
    except TaxMappingError as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e
