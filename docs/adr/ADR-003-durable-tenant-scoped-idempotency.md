# ADR-003 — Idempotency keys are stored in PostgreSQL, per tenant, and claimed after authentication

**Date:** 11 November 2026 · **Status:** accepted (implemented in `apps/api/idempotency.py`)

## Context

ARCHITECTURE.md Part D2 requires every mutating endpoint to be idempotent, and migration 001 created the
`idempotency_keys` table with primary key `(tenant_id, key)`. The audit of 11 November 2026 found that the
table was never used. `IdempotencyMiddleware` kept keys in a Python dictionary inside each API process:

1. **Not durable, not shared.** The API runs with two processes (`--workers 2` in `docker-compose.yml`).
   A retry that reached the other process, or arrived after a restart, ran the operation a second time.
2. **Not tenant-scoped.** The dictionary was keyed by the key alone. A second tenant sending the same key,
   method, path and body received the first tenant's stored answer.
3. **Replay before authentication.** The middleware answered before the session was resolved, so a stored
   answer was served without checking who was asking.
4. **Unbounded memory.** Entries were never removed.
5. **Server errors were kept.** A 503 ("try again later") was replayed for ever for that key.

## Decision

- Keys are rows of `idempotency_keys`. No schema change: the table from migration 001 is used as designed.
- The key is **claimed in `get_current_session`**, after the caller is authenticated and the tenant is known.
  The middleware still refuses a mutating request without a key (400) and hashes the body.
- Claim, completion and release each use their own short autocommit connection, with `app.tenant_id` set, so
  another process sees the claim while the handler is still running.
- Same key and same request: the stored answer is replayed (`Idempotency-Replay: true`). Same key and a
  different method, path or body: 422. Same key still running: 409.
- Answers with status 500 and above, and answers that are not JSON, are not kept: the key is freed.
- A claim older than 10 minutes that never completed (crashed process) is released. Completed keys are
  removed after 24 hours. Both durations are constants in `apps/api/idempotency.py`.

## Consequences

- One extra short database connection at the start and at the end of every mutating request. Acceptable at
  pilot volume; a connection pool is backlog item B-07.
- **Known limit:** the answer is recorded after the handler's transaction commits, not inside it. If the
  process dies between the two, the key stays "in progress" for 10 minutes, then the operation can run
  again. Exactly-once would need the key completed inside the handler's own transaction (TECHNICAL_DEBT D-03).
- Mutating routes that do not resolve a session have no stored key. None exists today.
- ARCHITECTURE.md is unchanged. The two durations should be recorded in Part K once a human approves them.
