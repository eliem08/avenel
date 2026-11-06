"""Session endpoints."""

from __future__ import annotations

from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends

from apps.api.deps import get_current_session, get_db
from avenel.tenancy.auth import UserSession

router = APIRouter(prefix="/v1", tags=["Session"])


@router.get("/me", summary="Get current authenticated user session")
async def get_me(
    session: Annotated[UserSession, Depends(get_current_session)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict[str, Any]:
    """Returns active session, tenant, role, and client scoping for authenticated user.

    Phase 5: also the professional title and registration number of the membership, shown on
    the approval page (Part E.5) and used to offer the approve action (the API still decides).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT professional_title, professional_registration_no FROM memberships WHERE tenant_id = %s AND id = %s;",
            (session.tenant_id, session.membership_id),
        )
        row = cur.fetchone()
    return {
        "professional_title": row[0] if row else None,
        "professional_registration_no": row[1] if row else None,
        "user_id": str(session.user_id),
        "tenant_id": str(session.tenant_id),
        "membership_id": str(session.membership_id),
        "role": session.role,
        "email": session.email,
        "full_name": session.full_name,
        "client_scope_ids": [str(c) for c in session.client_scope_ids],
    }
