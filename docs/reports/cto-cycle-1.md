# CTO execution cycle 1 — 11 November 2026

## Inspected

- The founder's two business documents and `ARCHITECTURE.md` (Parts A, C, D.1, D2, G, H, I, J).
  `AVENEL_MASTER_ARCHITECTURE_v2.md` does not exist in the repository.
- Repository layout, the 13 migrations, the 17 API route modules, `apps/api` middleware and dependencies,
  the worker, the document processing path, the AI provider router, the frontend routes and API client.
- Existing audits: `docs/roadmap/vision-gap.md`, `docs/open-questions.md`.

## Implemented

1. **Idempotency keys are now durable, per tenant, and claimed after authentication** (ADR-003).
   Before: kept in each API process's memory, keyed by the key alone, answered before authentication.
   New file `apps/api/idempotency.py`; `apps/api/middleware.py`, `apps/api/deps.py`, `apps/api/main.py` changed.
   No schema change: the `idempotency_keys` table from migration 001 is used. No domain logic touched.
2. **Migration-hash guard extended** to migrations 009–013 (`scripts/check_migration_hashes.py`).
3. **Documents:** `IMPLEMENTATION_STATUS.md`, `ARCHITECTURE_GAP_ANALYSIS.md`, `ENGINEERING_BACKLOG.md`,
   `TECHNICAL_DEBT.md`, `adr/ADR-003-…`.

## Tests actually run

| Check | Result |
|---|---|
| `pytest` full suite before the change | 327 passed |
| `pytest` full suite after the change | **332 passed** (5 new idempotency tests; 1 rewritten for the database store) |
| `ruff check avenel apps scripts` | passed |
| `mypy avenel apps/api scripts` | passed |
| Tax-literal guard, migration-hash guard (26 files), test-count guard | passed |
| `vitest` (frontend, before the change; frontend not modified) | 47 passed |
| Frontend type check, ESLint | passed |

New tests: the key is stored in PostgreSQL and replayed by a fresh store; the same key from another tenant
runs normally and never returns the first tenant's answer; a replay without authentication gets 401; a claim
left by a crashed process is released after the stale delay; server errors are not kept.

**Not run:** Playwright browser tests, front-end build, OpenAPI lint, `rls-check`. The change was **not**
exercised through the Docker stack's API. On the stack's database it was only checked that role `avenel_app`
has SELECT, INSERT, UPDATE and DELETE on `idempotency_keys` and that forced RLS allows the query.

## Remaining problems

- Worker is an empty loop; document reading runs inside the upload request with no retry (gap G-2).
- No AI provider connected (G-3); accuracy known on synthetic documents only (G-4).
- Sage / Odoo round trip not done (G-5); 42 `needs_expert` markers in the pack (G-6).
- Idempotency answer is recorded after the handler's commit (TECHNICAL_DEBT D-03).
- A test run rewrites a tracked benchmark file (D-11); an interrupted run can block the next one (D-08).
- Gazette crawl for 1912–1994 still running; four local commits not pushed.

## Next three priorities

1. Durable job queue and worker (B-01).
2. AI provider behind the router (B-02) — needs the founder's choice of provider and region.
3. Proof on a pilot firm's real documents and accounting software (B-03, B-04).
