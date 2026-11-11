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
| `pytest` full suite | **343 passed** (was 332): 11 new queue and worker tests, 1 API test rewritten; after the stack fix, the 17 job and document-reading tests pass (1 new) |
| `ruff`, `mypy` (101 files), tax-literal guard, migration-hash guard (28 files) | passed |
| OpenAPI lint (Spectral) | no errors |
| `vitest` | 47 passed |
| Frontend type check, ESLint | passed |

The rewritten API test (`test_ocr_engine_unavailable_queues_the_reading_and_the_worker_finishes_it`) replaces
`test_ocr_engine_unavailable_returns_503`: the behaviour changed on purpose from 503 to 202.

**Not run:** Playwright browser tests, front-end build, `rls-check`.

## Real-stack proof (11 November 2026, 15:00–15:12 UTC, Docker Compose stack)

Migration 014 applied by the `migrate` container; API and worker rebuilt from this commit. Two documents were
created in the seeded file `e526c9db…` **directly through the service functions** (`init_document_upload`,
`put_original`, `enqueue`) run inside the API container as `avenel_app` — **not through HTTP**, because the stack
API needs a Keycloak login with OTP. The 202 path itself was **not** triggered on the stack: OCR runs inside the
API process (RapidOCR), so stopping the `ocr` container (a stub) does not make it unavailable.

| Document | What the worker container did |
|---|---|
| A (original stored) | Claimed the job, read the scan, wrote the extraction (`FAC-2026-0412`, total TTC `12000.0`), job `succeeded`, attempt 1. |
| B (original missing) | Attempt 1 failed (`FileNotFoundError`), retry scheduled about 35 s later. Attempts 2–4 made due by hand, each logged `-> retry`, the fourth `-> failed`. Job `failed`, one blocking `INTEGRATION_FAILURE` issue opened on the document, evidence `attempts: 4`. |

### Problems found on the real stack and fixed

1. **Storage folder owned by root.** The gazette crawl container (run as root on 8 Nov) created the top folder of
   the shared `docstore` volume, so the API user (uid 10001) could not create `documents/`: every upload on this
   stack would have failed. Fixed by giving the folder to uid 10001; the crawl now runs as uid 10001.
2. **Stale virus signatures paused intake, and the worker turned the pause into a permanent quarantine.** ClamAV
   was serving March 2026 signatures (6,128 h old) because `freshclam` was not running. The product correctly
   paused intake, but the worker treated the pause like detected malware: job `succeeded`, documents
   `quarantined`, never read. **Fixed:** the worker now checks intake health first and retries a paused intake
   with backoff (`IntakePausedError`), with a regression test. `freshclam` started and `clamd` reloaded
   (signatures 9 h old).

Left as found: both proof documents stay `quarantined` from the first (buggy) run, although A has been read;
the status update skips quarantined documents by design. They and B's issue remain in the seeded file
`e526c9db…` and may need cleaning before the browser tests.

## Remaining problems

- Normal document reading still runs inside the upload request (TECHNICAL_DEBT D-02).
- Worker shares the API's database role (D-12); no per-job time limit (D-13); no screen refresh (D-14).
- The gazette crawl stopped when the session ended: it had added 117 issues (1994 back to 1990) and was in a
  pause after a dropped connection. 1912–1990 still to fetch.

## Next three priorities

1. Clean the two proof documents from the seeded file, then run the Playwright suite on the stack.
2. B-01 step 2: move the normal reading path to the queue, with status polling on the file screen.
3. AI provider behind the router (B-02) — needs the founder's choice of provider and region.
