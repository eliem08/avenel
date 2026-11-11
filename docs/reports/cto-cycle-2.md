# CTO execution cycle 2 — 11–12 November 2026

## Implemented (B-01 step 1, plan `docs/plans/b-01-job-queue.md`)

- **Migration 014** — table `jobs` (tenant-scoped, forced RLS, at most one active job per document and step,
  attempts capped at 4 by a database check) and `app.claim_next_job`, which hands a due job to exactly one
  worker (`FOR UPDATE SKIP LOCKED`) and re-issues jobs left running by a crashed worker.
- **`avenel/jobs/queue.py`** — enqueue, claim, success, failure with exponential backoff and jitter; after the
  fourth failure the job is `failed` and one blocking `INTEGRATION_FAILURE` issue is opened.
- **`avenel/jobs/worker.py`** — the empty loop is replaced by a real worker. The handler's writes and the job's
  `succeeded` state commit in one transaction; a failure rolls the writes back.
- **First use** — `POST /documents/{id}:complete-upload` with the reading engine down now answers **202**,
  queues a `read_document` job and sets the document to `processing` (before: 503 and nothing retried).
  Contract, generated TypeScript types and the upload screen message updated. The normal path is unchanged.
- No accounting, tax or approval logic touched. Migration 014 pinned in the hash guard.

## Tests actually run

| Check | Result |
|---|---|
| `pytest` full suite | **343 passed** (was 332): 11 new queue and worker tests, 1 API test rewritten |
| `ruff`, `mypy` (101 files), tax-literal guard, migration-hash guard (28 files) | passed |
| OpenAPI lint (Spectral) | no errors |
| `vitest` | 47 passed |
| Frontend type check, ESLint | passed |

The rewritten API test (`test_ocr_engine_unavailable_queues_the_reading_and_the_worker_finishes_it`) replaces
`test_ocr_engine_unavailable_returns_503`: the behaviour changed on purpose from 503 to 202.

**Not run:** Playwright browser tests, front-end build, `rls-check`. **Not done:** migration 014 is not applied
to the Docker database and the worker container has not been run with the new code — Docker Desktop was not
running at the end of this cycle. No test here is a real-stack proof.

## Remaining problems

- Normal document reading still runs inside the upload request (TECHNICAL_DEBT D-02).
- Worker shares the API's database role (D-12); no per-job time limit (D-13); no screen refresh (D-14).
- The gazette crawl stopped when the session ended: it had added 117 issues (1994 back to 1990) and was in a
  pause after a dropped connection. 1912–1990 still to fetch.

## Next three priorities

1. Apply migration 014 on the Docker stack and prove the retry there (stop OCR, upload, restart OCR).
2. B-01 step 2: move the normal reading path to the queue, with status polling on the file screen.
3. AI provider behind the router (B-02) — needs the founder's choice of provider and region.
