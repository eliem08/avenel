# AVENEL — Technical debt register

**Updated:** 11 November 2026. Debt is something that works today but will cost more later. Missing features
are in `ENGINEERING_BACKLOG.md`.

| # | Debt | Where | Consequence if left | Fix |
|---|---|---|---|---|
| D-01 | Document reading runs inside the upload request. | `apps/api/routes/documents.py::complete_upload`, `avenel/documents/service.py::process_uploaded_document` | Long requests, no automatic retry, work lost on a crash. | Backlog B-01. |
| D-02 | The worker only handles readings that failed in the upload request; the normal path is still synchronous. | `avenel/jobs/worker.py`, `apps/api/routes/documents.py` | Long upload requests remain. | B-01 step 2. |
| D-03 | The idempotency answer is saved after the handler's commit, in a separate connection. | `apps/api/idempotency.py`, ADR-003 | A crash between the two lets the operation run again after 10 minutes. | Complete the key inside the handler's transaction, or make each handler naturally idempotent. |
| D-04 | No connection pool; each request opens a connection, plus one for rate limiting and two for idempotency. | `apps/api/deps.py`, `apps/api/middleware.py` | Connection exhaustion under load. | B-07. |
| D-05 | The rate limiter falls back to per-process memory when the database is unreachable. | `apps/api/middleware.py::RateLimitStore` | Limits are not shared between processes during an outage. | Decide: fail closed or keep the fallback; record in Part K. |
| D-06 | `AGENTS.md` names ARCHITECTURE.md "Version 2.0"; reports mention v2.1. | `AGENTS.md` | Confusion about the binding version. | Align on the next ARCHITECTURE.md edit. |
| D-07 | The migration-hash list is maintained by hand. | `scripts/check_migration_hashes.py` | A new migration is unprotected until someone pins it (009–013 were unpinned until 11 Nov 2026). | Fail CI when a migration older than the newest one is not pinned. |
| D-08 | The test suite starts its own PostgreSQL; an interrupted run can leave a worker process holding port 5439, and the next run hangs for minutes. | `tests/conftest.py` | Lost time; looks like a code failure. Seen on 11 Nov 2026. | Stop the cluster in a `finally`, or pick a free port. |
| D-09 | The legal-source crawler's 5-minute download cap is not tested against a real stalled connection. | `avenel/knowledge/crawler.py` | A crawl could hang for hours again. | Add a hard wall-clock timeout around each fetch. |
| D-10 | Accuracy numbers come from synthetic documents. | `docs/benchmarks/` | False confidence. | B-03. |
| D-11 | A test run rewrites the date line of a tracked file. | `docs/benchmarks/synthetic-pipeline-test.md` | Every local test run leaves a modified file in the working tree. | Write the benchmark report outside the tracked tree, or only on request. |
| D-12 | The worker uses the `avenel_app` role, which may call `app.claim_next_job` and so learn job and tenant identifiers of every tenant (identifiers only, server side). | migration 014 | The API role has a cross-tenant capability it does not need. | A separate `avenel_worker` role; revoke EXECUTE from `avenel_app`. |
| D-13 | Job handlers run with no time limit; a hung handler holds the job for the 15-minute stale delay. | `avenel/jobs/worker.py` | Slow recovery from a hang. | Per-step timeout. |
| D-14 | The upload screen says the reading "will resume automatically" but does not refresh when it does. | `src/screens/FileScreen.tsx` | The user must reload to see the result. | B-01 step 2 (status polling). |
| D-15 | When clamd does not answer `VERSION`, the signature check reports "fresh" (age 0); seen during a reload on 11 Nov 2026. | `avenel/documents/scanner.py` | Intake may run without a known signature age. Needs review: does the separate availability check stop it? | Treat an unknown age as stale. |
| D-16 | Nothing alerts when `freshclam` is stopped; the stack ran on 8-month-old signatures until intake paused itself. | `docker-compose.yml` | Intake stops with no warning to operators beforehand. | Health check or alert on signature age. |
| D-17 | Containers that share the `docstore` volume must all run as uid 10001; one root container broke uploads. | `docker-compose.yml`, ops scripts | Silent upload failures. | Create the folder with the right owner at start-up, or check it in `/health/ready`. |
