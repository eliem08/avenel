"""Bank accounts and statement ingestion API routes (Phase 4)."""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

import psycopg
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from apps.api.deps import get_current_session, get_db
from avenel.bank.service import (
    create_bank_account,
    ingest_bank_statement,
    list_bank_accounts,
)
from avenel.documents.scanner import (
    check_intake_health,
    record_scan_evidence,
    scan_bytes,
)
from avenel.infrastructure.storage import compute_sha256, get_storage
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1/bank-accounts", tags=["Bank"])


class CreateBankAccountInput(BaseModel):
    client_entity_id: uuid.UUID
    rib: str = Field(..., description="Moroccan 24-digit RIB")
    currency: str = Field(default="MAD", max_length=3)
    journal_code: str = Field(default="BQ")


class BankAccountResponse(BaseModel):
    id: uuid.UUID
    bank_code: str
    rib_last4: str
    rib_masked: str
    currency: str
    journal_code: str


def _check_client_scope(session: UserSession, client_id: uuid.UUID) -> None:
    if session.role == "client_user" and client_id not in session.client_scope_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")


@router.post("", status_code=status.HTTP_201_CREATED)
def register_bank_account_endpoint(
    payload: CreateBankAccountInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Registers a new bank account with Moroccan RIB validation."""
    _check_client_scope(session, payload.client_entity_id)

    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    try:
        return create_bank_account(
            conn=conn,
            tenant_id=session.tenant_id,
            client_entity_id=payload.client_entity_id,
            rib=payload.rib,
            currency=payload.currency,
            journal_code=payload.journal_code,
            actor_id=str(session.user_id),
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)) from err


@router.get("")
def list_bank_accounts_endpoint(
    client_entity_id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Lists bank accounts for a specific client entity."""
    _check_client_scope(session, client_entity_id)
    return list_bank_accounts(conn, session.tenant_id, client_entity_id)


statements_router = APIRouter(prefix="/v1/bank-statements", tags=["Bank"])


@statements_router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_bank_statement_endpoint(
    client_entity_id: Annotated[uuid.UUID, Form()],
    bank_account_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    response: Response,
    work_request_id: Annotated[uuid.UUID | None, Form()] = None,
) -> dict[str, Any]:
    """Uploads and ingests a bank statement with balance verification."""
    _check_client_scope(session, client_entity_id)

    if session.role in ("client_user", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour ce rôle.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide.")

    # Phase 4 completion: a statement is an upload like any other (Part K 8, K 9).
    # 1. The bank account must belong to this client company (scope-first 404).
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM bank_accounts WHERE tenant_id = %s AND client_entity_id = %s AND id = %s;",
            (session.tenant_id, client_entity_id, bank_account_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte bancaire introuvable.")
    # 2. Intake paused (antivirus down or signatures stale): refuse, nothing stored.
    health = check_intake_health()
    if health.intake_paused:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health.banner_message)
    # 3. Exact duplicate of a statement already received for this company.
    file_sha256 = compute_sha256(file_bytes)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT document_id FROM document_versions WHERE tenant_id = %s AND client_entity_id = %s AND sha256 = %s;",
            (session.tenant_id, client_entity_id, file_sha256),
        )
        dup = cur.fetchone()
    if dup:
        response.status_code = status.HTTP_200_OK
        return {
            "document_id": str(dup[0]),
            "resubmitted": True,
            "detail": "Ce relevé a déjà été reçu pour cette société. Il n'est pas importé une seconde fois.",
        }
    # 4. Malware scan before anything is parsed or stored as an original.
    scan = scan_bytes(file_bytes)

    # Create document version for audit/storage
    doc_id = uuid.uuid4()
    doc_version_id = uuid.uuid4()
    storage = get_storage()
    object_key = f"documents/{session.tenant_id}/{client_entity_id}/{doc_id}/v1"
    mime_type = file.content_type or "text/csv"

    if scan.is_clean:
        # retain_until unset: retention period is needs_expert in the pack (TODO(EXPERT)).
        storage.put_original(object_key, file_bytes, mime_type, retain_until=None)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (
                id, tenant_id, client_entity_id, work_request_id,
                doc_type, status, original_filename, source_channel, uploaded_by
            )
            VALUES (%s, %s, %s, %s, 'bank_statement', %s, %s, 'console', %s);
            """,
            (
                doc_id,
                session.tenant_id,
                client_entity_id,
                work_request_id,
                "received" if scan.is_clean else "quarantined",
                file.filename or "releve_bancaire.csv",
                session.user_id,
            ),
        )
        cur.execute(
            """
            INSERT INTO document_versions (
                id, tenant_id, client_entity_id, document_id, version_number,
                object_key, sha256, mime_type, byte_size, page_count
            )
            VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, 1);
            """,
            (
                doc_version_id,
                session.tenant_id,
                client_entity_id,
                doc_id,
                object_key,
                file_sha256,
                mime_type,
                len(file_bytes),
            ),
        )

    if not scan.is_clean:
        with conn.cursor() as cur:
            if work_request_id:
                record_scan_evidence(conn, session.tenant_id, work_request_id, doc_id, scan)
                cur.execute(
                    """INSERT INTO issues (tenant_id, client_entity_id, work_request_id, subject_document_id,
                                           code, severity, status, evidence_refs)
                       VALUES (%s, %s, %s, %s, 'DOC_MALWARE', 'blocking', 'open', %s::jsonb);""",
                    (session.tenant_id, client_entity_id, work_request_id, doc_id, json.dumps([scan.details or {}])),
                )
        conn.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Relevé mis en quarantaine : logiciel malveillant détecté ({scan.threat_name}). Il n'est pas importé.",
        )

    try:
        res = ingest_bank_statement(
            conn=conn,
            tenant_id=session.tenant_id,
            client_entity_id=client_entity_id,
            bank_account_id=bank_account_id,
            document_id=doc_id,
            file_bytes=file_bytes,
            filename=file.filename or "releve.csv",
            work_request_id=work_request_id,
            actor_id=str(session.user_id),
        )
        return res
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)) from err
