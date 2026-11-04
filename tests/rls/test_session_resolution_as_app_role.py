"""Regression test (Phase 5c-1): login failed for every real user under the app role.

resolve_user_session read `memberships` before setting the tenant context, so under
forced RLS as `avenel_app` (Part C.5) the row was hidden and every OIDC login got 401.
API tests did not catch it because they connect as a superuser.
"""

from __future__ import annotations

import uuid

import psycopg

from avenel.tenancy.auth import resolve_user_session
from tests.helpers import seed_membership, seed_tenant, seed_user


def test_resolve_user_session_works_as_avenel_app(db_conn: psycopg.Connection, app_conn: psycopg.Connection) -> None:
    t_id = seed_tenant(db_conn, "Cabinet RLS Resolution")
    sub = f"rls-resolve-{uuid.uuid4()}"
    u_id = seed_user(db_conn, identity_subject=sub, email=f"{sub}@example.com")
    seed_membership(db_conn, u_id, t_id, role="accountant")
    db_conn.commit()

    session = resolve_user_session(app_conn, sub)

    assert session is not None
    assert session.tenant_id == t_id
    assert session.user_id == u_id
    assert session.role == "accountant"


def test_resolve_user_session_as_avenel_app_unknown_subject_is_none(app_conn: psycopg.Connection) -> None:
    assert resolve_user_session(app_conn, f"nobody-{uuid.uuid4()}") is None
