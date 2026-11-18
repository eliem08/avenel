# AVENEL — Technical debt register

**Updated:** 11 November 2026. Debt is something that works today but will cost more later. Missing features
are in `ENGINEERING_BACKLOG.md`.

| # | Debt | Where | Consequence if left | Fix |
|---|---|---|---|---|
| D-01 | Document reading runs inside the upload request. | `apps/api/routes/documents.py::complete_upload`, `avenel/documents/service.py::process_uploaded_document` | Long requests, no automatic retry, work lost on a crash. | Backlog B-01. |
| D-02 | Background reading exists but is off by default (`AVENEL_READ_IN_BACKGROUND`); with it off, readings still run inside the upload request. | `avenel/jobs/worker.py`, `apps/api/routes/documents.py` | Long upload requests remain. | B-01 step 2. |
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
| D-14 | The upload screen polls the document status every 3 s for at most 10 minutes; a reading retried later (backoff) is only seen after a reload. | `src/screens/FileScreen.tsx` | The user may have to reload after a long outage. | Server push or a list-level refresh. |
| D-15 | Fixed 13 Nov 2026: an unknown signature age now pauses intake (outside the test fixture). | `avenel/documents/scanner.py` | — | Done; test `test_unknown_signature_age_pauses_intake`. |
| D-16 | Nothing alerts when `freshclam` is stopped; the stack ran on 8-month-old signatures until intake paused itself. | `docker-compose.yml` | Intake stops with no warning to operators beforehand. | Health check or alert on signature age. |
| D-17 | Containers that share the `docstore` volume must all run as uid 10001; one root container broke uploads. | `docker-compose.yml`, ops scripts | Silent upload failures. | Create the folder with the right owner at start-up, or check it in `/health/ready`. |
| D-18 | Fixed 15 Nov 2026: browser tests assumed a fresh stack. Each run now uses unique file names, a new client company (with its own ICE) for phase 3, and a unique EICAR file. The EICAR one matters: on a reused stack the identical EICAR bytes were refused as already received, so the malware check passed without any scan. | `e2e/phase2-intake.spec.ts`, `e2e/phase3-proposals.spec.ts` | 3 browser tests passed twice in a row on the same used stack (15 Nov). | Done. |
| D-19 | Fixed 13 Nov 2026: the test-only scanner fixture was on by default and no compose file turned it off, so with ClamAV unreachable or slow (1 s limit) an upload passed as clean without a real scan. Now off by default, the scan limit is 30 s (`AVENEL_CLAMAV_SCAN_TIMEOUT_SECONDS`), and the worker retries a "scanner unavailable" result instead of quarantining. | `avenel/documents/scanner.py`, `avenel/jobs/worker.py` | Documents read before this fix may have been passed by the fixture: 2 on the dev stack. | Done; tests added. 18 Nov 2026: the offline mode is removed from production code entirely (it had failed the Part K 25 guard, and so CI, since 15 Nov); the test suite now scans through a stand-in clamd on a local socket (`tests/clamd_stub.py`). Re-scan earlier documents before any pilot. |
| D-20 | On the dev stack, freshclam stopped checking for updates for about 24 h, and clamd missed one reload (its connection was refused at the time). Signatures reached 67.8 h old and intake paused, as designed. A freshclam restart fixed it. | `docker-compose.yml` (freshclam, clamav) | Intake stops until someone acts; there is no alert outside the API log. | Health check on the signature age in the freshclam/clamav containers, plus an alert on `clamav_intake_paused`. |
| D-21 | Fixed 15 Nov 2026: a second client with the same ICE (or a second client without ICE, because of `UNIQUE NULLS NOT DISTINCT` in migration 001) crashed the API with a 500. It now gets a 409 with a French message. Allowing several clients without an ICE is a product decision and is still open. | `apps/api/routes/clients.py` | A firm can register only one client without an ICE. | Decide whether to allow several clients without an ICE (this needs a new migration). |
| D-22 | AI provider (B-02) is NVIDIA's hosted API, which is outside Morocco and the EU. It is used only by firms set to GLOBAL_ALLOWED; on the dev stack that is only the synthetic demo firm, with the founder's approval of 15 Nov 2026. Identifiers are masked, but names, addresses and amounts still leave the country. The free endpoint is slow (about 45 s per page) and sometimes answers 503. The model asked for, `moonshotai/kimi-k3.1-pro`, does not exist on this key, and `kimi-k2.6` answers 404, so MiniMax M3.1 Flash is used instead. | `avenel/extraction/ai_fill.py`, `docker-compose.yml` | No real client data may use it before a CNDP route exists (Part I item 8). | CNDP decision; a paid or Morocco/EU-hosted endpoint; a field-level accuracy run (B-03). |

## D-23 — Duplicate RIB returns 500, and browser tests reuse a fixed RIB (found 17 Nov 2026)
`POST /v1/bank-accounts` with a RIB already registered in the firm raises `UniqueViolation`
(`bank_accounts_tenant_id_rib_sha256_key`) and the API answers 500; it should answer 409 with a clear message,
as D-21 did for a duplicate ICE. The phase 4 and phase 6 browser tests use a fixed RIB, so on a reused stack
their second run fails at "Ajouter le compte". Fix: map the violation to 409 and give each run a fresh valid
RIB (key computed per run). Not fixed in phase 8a.

**Fixed 18 Nov 2026:** the API answers 409 "Ce RIB est déjà enregistré dans ce cabinet." (test
`test_same_rib_twice_is_a_conflict_not_a_server_error`), and the phase 4 and 6 browser tests use a fresh RIB
(`e2e/rib.ts`). Phase 4 statements also carry a run reference. **Still open:** phase 4 reconciles a single
seeded invoice that an earlier run has already matched, so a second run finds nothing to match; it needs a
fresh company and invoice per run, as phase 3 has.

**Fixed 18 Nov 2026:** phase 4 now creates its own company, September file, approved VAT account and invoice
entry each run, so its reconciliation no longer depends on the seeded "Atlas Distribution SARL" invoice.

## D-20 (again, 18 Nov 2026)
Freshclam stalled a second time: signatures reached 53 h and intake paused until freshclam was restarted.
Restarting by hand is not a fix; freshclam needs a health check that restarts it when signatures pass 24 h.

**Changed 18 Nov 2026:** the freshclam daemon is replaced by `docker/clamav/freshclam-loop.sh`: one run per
hour, each a new process killed after 15 min, so a stuck run no longer holds updates (restarting the container
by hand did exactly this). `docker/clamav/freshclam-health.sh` marks the container unhealthy when no run
succeeded in 2 h or the daily signatures are 24 h old (checked on the stack: healthy, a 2.5 h old run, no run,
and the 24 h case with the clock moved forward in a copy of the script). Still open: Docker Compose does not
restart an unhealthy container and nothing alerts a person yet; that needs production monitoring (an alert on
the health status and on `clamav_intake_paused`).

## D-24 — Asking for approval again while one is pending answers 500 (found 18 Nov 2026)
`avenel/approvals/service.py` cancels the earlier pending approval with only `status = 'cancelled'`. Migration
001 requires a decided approval to record who decided, when and why, and forbids the person who prepared the
file from deciding on it (unless the firm allows one-person approval). So the second request crashes (checked
through the API: 201, then 500). It has been there since phase 5; no test covered it, and the phase 8c report
wrongly said it worked. Phase 8d's cancel does record who, when and why, and refuses the preparer.
**Needs a decision:** refuse a second request while one is pending (409), or let a different person withdraw
the pending one first.

