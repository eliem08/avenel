"""Chart of accounts endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.accounting.chart_import import (
    MAX_FILE_BYTES,
    parse_csv_chart,
    parse_xlsx_chart,
)
from avenel.accounting.service import (
    import_chart_accounts,
    list_chart_accounts,
    seed_cgnc_chart,
)
from avenel.clients.service import (
    ClientArchivedError,
    ClientNotFoundError,
    get_client_entity,
)
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Chart"])


class AccountItem(BaseModel):
    code: str
    label: str


class ImportChartInput(BaseModel):
    accounts: list[AccountItem]


@router.get("/client-entities/{id}/chart-accounts", summary="List chart of accounts for client company")
async def get_chart_accounts(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Lists chart accounts. Cross-tenant or out-of-scope returns 404."""
    scope = session.client_scope_ids if session.role == "client_user" else None
    client = get_client_entity(conn, session.tenant_id, id, client_scope_ids=scope)
    if not client:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    try:
        items = list_chart_accounts(conn, session.tenant_id, id)
        return {"items": items}
    except ClientNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/client-entities/{id}/chart-accounts/seed-cgnc", summary="Seed standard Moroccan CGNC chart accounts")
async def seed_chart(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    """Seeds Moroccan CGNC core accounts. Cross-tenant or out-of-scope returns 404. In-scope forbidden returns 403."""
    # Scope check first: out-of-scope returns 404
    if session.role == "client_user" and id not in session.client_scope_ids:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    client = get_client_entity(conn, session.tenant_id, id)
    if not client:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    # Action permission check: in-scope but unauthorized role returns 403
    if session.role in ("staff", "client_user", "operator"):
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    try:
        count = seed_cgnc_chart(conn, session.tenant_id, id, actor_id=str(session.user_id))
        conn.commit()
        return {
            "seeded_count": count,
            "message": f"{count} comptes standards CGNC configurés avec succès.",
        }
    except ClientArchivedError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ClientNotFoundError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/client-entities/{id}/chart-accounts/import", summary="Import chart of accounts from CSV or XLSX")
async def import_chart(
    id: uuid.UUID,
    body: ImportChartInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, Any]:
    """Imports chart accounts. Cross-tenant or out-of-scope returns 404. In-scope forbidden returns 403."""
    # Scope check first: out-of-scope returns 404
    if session.role == "client_user" and id not in session.client_scope_ids:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    client = get_client_entity(conn, session.tenant_id, id)
    if not client:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")

    # Action permission check: in-scope but unauthorized role returns 403
    if session.role in ("staff", "client_user", "operator"):
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    try:
        account_tuples = [(a.code, a.label) for a in body.accounts]
        count = import_chart_accounts(conn, session.tenant_id, id, actor_id=str(session.user_id), accounts=account_tuples)
        conn.commit()
        return {
            "imported_count": count,
            "message": f"{count} comptes importés avec succès.",
        }
    except ClientArchivedError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ClientNotFoundError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/client-entities/{id}/chart-accounts/import-file",
    summary="Import chart of accounts from a CSV or XLSX file",
    operation_id="importChartAccountsFile",
)
async def import_chart_file(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    file: Annotated[UploadFile, File(description="Chart of accounts, .csv or .xlsx")],
) -> dict[str, Any]:
    """Parses the file with the hardened CSV/XLSX parsers, then imports like the JSON endpoint.

    Same rules: out-of-scope or other tenant -> 404, in-scope forbidden role -> 403.
    """
    if session.role == "client_user" and id not in session.client_scope_ids:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")
    client = get_client_entity(conn, session.tenant_id, id)
    if not client:
        raise HTTPException(status_code=404, detail="Entreprise cliente introuvable.")
    if session.role in ("staff", "client_user", "operator"):
        raise HTTPException(status_code=403, detail="Action non autorisée pour ce rôle.")

    name = (file.filename or "").lower()
    content = await file.read(MAX_FILE_BYTES + 1)
    try:
        if name.endswith(".csv"):
            accounts = parse_csv_chart(content)
        elif name.endswith(".xlsx"):
            accounts = parse_xlsx_chart(content)
        else:
            raise HTTPException(
                status_code=415,
                detail="Format non pris en charge. Importez un fichier .csv ou .xlsx.",
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not accounts:
        raise HTTPException(status_code=422, detail="Le fichier ne contient aucun compte.")

    try:
        count = import_chart_accounts(conn, session.tenant_id, id, actor_id=str(session.user_id), accounts=accounts)
        conn.commit()
    except ClientArchivedError as e:
        conn.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ClientNotFoundError as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"imported_count": count, "message": f"{count} comptes importés avec succès."}
