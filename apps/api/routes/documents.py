"""Document inspection, processing completion, and extraction field correction routes."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from apps.api.deps import get_current_session, get_db
from avenel.documents.service import (
    DocumentNotFoundError,
    InvalidDocumentPayloadError,
    QuarantineError,
    correct_extraction_fields,
    process_uploaded_document,
)
from avenel.infrastructure.storage import MAX_DOCUMENT_BYTE_SIZE, get_storage
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Documents"])


class ExtractionPatchInput(BaseModel):
    fields: dict[str, Any]


def _resolve_document_scope(
    conn: psycopg.Connection,
    session: UserSession,
    document_id: uuid.UUID,
) -> dict[str, Any]:
    """Scope-first resolution: returns document details or raises 404."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.client_entity_id, d.work_request_id, d.original_filename,
                   d.status, d.doc_type, dv.page_count, d.received_at
            FROM documents d
            LEFT JOIN document_versions dv ON dv.document_id = d.id AND dv.tenant_id = d.tenant_id
            WHERE d.tenant_id = %s AND d.id = %s
            LIMIT 1;
            """,
            (session.tenant_id, document_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        client_entity_id = uuid.UUID(str(row[1]))
        if session.role == "client_user" and client_entity_id not in session.client_scope_ids:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        return {
            "id": str(row[0]),
            "client_entity_id": str(row[1]),
            "work_request_id": str(row[2]) if row[2] else None,
            "original_filename": row[3],
            "status": row[4],
            "doc_type": row[5],
            "page_count": row[6],
            "received_at": row[7].isoformat() if row[7] else None,
        }


@router.get("/documents/{id}")
async def get_document(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    return _resolve_document_scope(conn, session, id)


@router.put("/documents/{id}/content", operation_id="uploadDocumentContent")
async def upload_document_content(
    id: uuid.UUID,
    request: Request,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Stores the original bytes of a document initialised by POST /work-requests/{id}/uploads.

    Human decision (Phase 2, 6 Nov 2026): uploads go through the API, for every storage backend.
    The body must match the size and SHA-256 declared at init (duplicate detection and evidence
    rely on that hash). Originals are write-once: a second upload for the same version is refused.
    """
    _resolve_document_scope(conn, session, id)
    if session.role == "operator":
        raise HTTPException(status_code=403, detail="Les opérateurs ne peuvent pas téléverser de documents.")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT dv.object_key, dv.byte_size, dv.sha256, dv.mime_type
            FROM document_versions dv
            WHERE dv.tenant_id = %s AND dv.document_id = %s
            ORDER BY dv.version_number DESC
            LIMIT 1;
            """,
            (session.tenant_id, id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    object_key, byte_size, sha256, mime_type = str(row[0]), int(row[1]), str(row[2]).lower(), str(row[3])

    storage = get_storage()
    if storage.object_exists(object_key):
        raise HTTPException(status_code=409, detail="Le fichier original de cette pièce est déjà enregistré.")

    data = bytearray()
    limit = min(byte_size, MAX_DOCUMENT_BYTE_SIZE)
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail="Le fichier est plus volumineux que la taille déclarée.")
    if len(data) != byte_size:
        raise HTTPException(status_code=422, detail="La taille du fichier reçu ne correspond pas à la taille déclarée.")
    if hashlib.sha256(bytes(data)).hexdigest() != sha256:
        raise HTTPException(status_code=422, detail="L'empreinte SHA-256 du fichier reçu ne correspond pas à celle déclarée.")

    # retain_until stays unset: the retention period is needs_expert in the pack
    # (compliance.documents.retention_years_after_fiscal_year_end, TODO(EXPERT)).
    storage.put_original(object_key, bytes(data), mime_type, retain_until=None)
    return {"document_id": str(id), "byte_size": byte_size, "sha256": sha256, "stored": True}


@router.post("/documents/{id}:complete-upload")
async def complete_upload(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    # 1. Scope-first check: 404 if out of scope
    _resolve_document_scope(conn, session, id)

    # 2. Role permission check: operator cannot trigger document processing
    if session.role == "operator":
        raise HTTPException(status_code=403, detail="Les opérateurs ne peuvent pas lancer le traitement de documents.")

    try:
        res = process_uploaded_document(
            conn=conn,
            tenant_id=session.tenant_id,
            document_id=id,
        )
        conn.commit()
        return {
            "document_id": res["document_id"],
            "doc_type": res["doc_type"],
            "status": res["status"],
            "extraction_id": res["extraction_id"],
            "validation": res["validation"],
        }
    except QuarantineError as err:
        conn.commit()
        raise HTTPException(status_code=422, detail=str(err)) from err
    except (InvalidDocumentPayloadError, ValueError) as err:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(err)) from err


@router.get("/documents/{id}/pages/{n}")
async def get_document_page(
    id: uuid.UUID,
    n: int,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    # 1. Scope-first check
    _resolve_document_scope(conn, session, id)

    storage = get_storage()
    page_key = f"pages/{session.tenant_id}/{id}/page_{n}.png"
    img_url = storage.generate_presigned_get_url(page_key)

    return {
        "page_number": n,
        "image_url": img_url,
        "media_type": "image/png",
    }


@router.get("/documents/{id}/extraction")
async def get_document_extraction(
    id: uuid.UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    # 1. Scope-first check
    _resolve_document_scope(conn, session, id)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, e.fields, e.validation
            FROM extractions e
            JOIN document_versions dv ON dv.id = e.document_version_id AND dv.tenant_id = e.tenant_id
            WHERE e.tenant_id = %s AND dv.document_id = %s
            ORDER BY e.created_at DESC
            LIMIT 1;
            """,
            (session.tenant_id, id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Extraction introuvable pour ce document.")

        fields = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        validation = row[2] if isinstance(row[2], dict) else json.loads(row[2])

        return {
            "extraction_id": str(row[0]),
            "fields": fields,
            "validation": validation,
        }


@router.patch("/documents/{id}/extraction")
async def correct_extraction(
    id: uuid.UUID,
    body: ExtractionPatchInput,
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    # 1. Scope-first check
    _resolve_document_scope(conn, session, id)

    # 2. Role check: operator and client_user cannot correct extraction fields
    if session.role in ("operator", "client_user"):
        raise HTTPException(status_code=403, detail=f"Le rôle '{session.role}' ne peut pas corriger les extractions comptables.")

    try:
        res = correct_extraction_fields(
            conn=conn,
            tenant_id=session.tenant_id,
            document_id=id,
            field_updates=body.fields,
        )
        conn.commit()
        return res
    except DocumentNotFoundError as err:
        conn.rollback()
        raise HTTPException(status_code=404, detail=str(err)) from err