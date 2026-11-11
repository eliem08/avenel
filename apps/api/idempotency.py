"""Durable, tenant-scoped idempotency for mutating API requests (ARCHITECTURE.md Part D2, ADR-003).

Keys live in the `idempotency_keys` table (migration 001), primary key `(tenant_id, key)`, so that:
- a retry is recognised by every API process and after a restart;
- a key used by one tenant never matches another tenant's request;
- a stored answer is only replayed to a caller who has just been authenticated for that tenant.

The key is claimed in `get_current_session` (after authentication) and completed by
`IdempotencyMiddleware` once the handler has answered. Each step uses its own short autocommit
connection, so the claim is visible to other processes while the handler is still running.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from starlette.responses import JSONResponse, Response

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
STALE_IN_PROGRESS_MINUTES = 10  # a claim left by a crashed process is released after this long
COMPLETED_RETENTION_HOURS = 24  # answers are kept for replay this long, then cleaned up


@dataclass(frozen=True)
class Claim:
    outcome: str  # "started" | "in_progress" | "mismatch" | "replay"
    response_code: int | None = None
    response_body: Any = None


class IdempotencyShortCircuit(Exception):
    """Raised from the session dependency to answer without running the handler."""

    def __init__(self, response: Response) -> None:
        super().__init__("idempotency short circuit")
        self.response = response


def _problem(status: int, slug: str, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={"type": f"https://avenel.ma/errors/{slug}", "title": title, "status": status, "detail": detail},
    )


class PgIdempotencyStore:
    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    def _connect(self, tenant_id: uuid.UUID) -> psycopg.Connection:
        conn = psycopg.connect(self._db_url, autocommit=True)
        conn.execute("SELECT set_config('app.tenant_id', %s, false);", (str(tenant_id),))
        return conn

    def claim(self, tenant_id: uuid.UUID, key: str, method: str, path: str, request_sha256: str) -> Claim:
        with self._connect(tenant_id) as conn:
            conn.execute(
                """
                DELETE FROM idempotency_keys
                WHERE tenant_id = %s
                  AND ((status = 'in_progress' AND created_at < now() - make_interval(mins => %s))
                    OR (status = 'completed' AND created_at < now() - make_interval(hours => %s)));
                """,
                (tenant_id, STALE_IN_PROGRESS_MINUTES, COMPLETED_RETENTION_HOURS),
            )
            inserted = conn.execute(
                """
                INSERT INTO idempotency_keys (tenant_id, key, method, path, request_sha256, status)
                VALUES (%s, %s, %s, %s, %s, 'in_progress')
                ON CONFLICT (tenant_id, key) DO NOTHING
                RETURNING key;
                """,
                (tenant_id, key, method, path, request_sha256),
            ).fetchone()
            if inserted:
                return Claim("started")
            row = conn.execute(
                """
                SELECT method, path, request_sha256, status, response_code, response_body
                FROM idempotency_keys WHERE tenant_id = %s AND key = %s;
                """,
                (tenant_id, key),
            ).fetchone()
        if row is None:  # removed between the two statements: the caller may simply retry
            return Claim("in_progress")
        if (row[0], row[1], str(row[2])) != (method, path, request_sha256):
            return Claim("mismatch")
        if row[3] != "completed":
            return Claim("in_progress")
        return Claim("replay", int(row[4]), row[5])

    def complete(self, tenant_id: uuid.UUID, key: str, response_code: int, response_body: Any) -> None:
        with self._connect(tenant_id) as conn:
            conn.execute(
                """
                UPDATE idempotency_keys
                SET status = 'completed', response_code = %s, response_body = %s
                WHERE tenant_id = %s AND key = %s AND status = 'in_progress';
                """,
                (response_code, Jsonb(response_body) if response_body is not None else None, tenant_id, key),
            )

    def release(self, tenant_id: uuid.UUID, key: str) -> None:
        with self._connect(tenant_id) as conn:
            conn.execute(
                "DELETE FROM idempotency_keys WHERE tenant_id = %s AND key = %s AND status = 'in_progress';",
                (tenant_id, key),
            )


def claim_or_short_circuit(store: PgIdempotencyStore, request: Any, tenant_id: uuid.UUID) -> None:
    """Called once the caller is authenticated. Claims the key or raises the ready answer."""
    key = getattr(request.state, "idempotency_key", None)
    if request.method not in MUTATING_METHODS or not key:
        return
    claim = store.claim(tenant_id, key, request.method, request.url.path, request.state.idempotency_sha256)
    if claim.outcome == "started":
        request.state.idempotency_claim = (tenant_id, key)
        return
    if claim.outcome == "in_progress":
        raise IdempotencyShortCircuit(_problem(
            409, "concurrent-idempotent-request", "Concurrent Request In Progress",
            "Une requête avec cette clé d'idempotence est actuellement en cours d'exécution.",
        ))
    if claim.outcome == "mismatch":
        raise IdempotencyShortCircuit(_problem(
            422, "idempotency-key-mismatch", "Idempotency Key Reused With Different Body",
            "La clé d'idempotence a déjà été utilisée avec un corps de requête différent.",
        ))
    code = claim.response_code or 200
    headers = {"Idempotency-Replay": "true"}
    if claim.response_body is None:
        raise IdempotencyShortCircuit(Response(status_code=code, headers=headers))
    media = "application/problem+json" if code >= 400 else "application/json"
    raise IdempotencyShortCircuit(
        JSONResponse(status_code=code, content=claim.response_body, headers=headers, media_type=media)
    )


def finish(store: PgIdempotencyStore, request: Any, status_code: int, body: bytes) -> None:
    """Called by the middleware after the handler answered. Server errors are never kept."""
    claim = getattr(request.state, "idempotency_claim", None)
    if claim is None:
        return
    tenant_id, key = claim
    if status_code >= 500:
        store.release(tenant_id, key)
        return
    if not body:
        store.complete(tenant_id, key, status_code, None)
        return
    try:
        parsed = json.loads(body)
    except ValueError:  # not JSON: cannot be replayed faithfully, so the key is freed
        store.release(tenant_id, key)
        return
    store.complete(tenant_id, key, status_code, parsed)


def abandon(store: PgIdempotencyStore, request: Any) -> None:
    claim = getattr(request.state, "idempotency_claim", None)
    if claim is not None:
        store.release(*claim)
