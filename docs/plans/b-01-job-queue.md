# Plan — B-01 durable job queue and worker (step 1)

**Date:** 11 November 2026 · **Spec:** ARCHITECTURE.md C.1 (one worker process), D.1 ("Each job is
idempotent: keyed by `(work_request_id, step, revision)`. Retries use exponential backoff with jitter, max 4
attempts, then raise an `integration` issue.") · **Gap:** G-2 in `docs/ARCHITECTURE_GAP_ANALYSIS.md`.

## Problem

`avenel/jobs/worker.py` sleeps for ever. Reading a document (scan, render, OCR, classify, extract, validate)
runs inside `POST /documents/{id}:complete-upload`. When the OCR engine is down the request answers 503 and
nothing retries.

## Step 1 (this change): the queue, the worker, and one real use

1. **Migration 014** — table `jobs`, tenant-scoped with forced RLS like every tenant table.
   - Key: `(tenant_id, work_request_id, step, subject_id, revision)`. `subject_id` is added to the spec's key
     because one monthly file has many documents and each is read separately.
   - At most one active job (`queued` or `running`) per `(tenant, step, subject)`.
   - `attempts` cannot exceed 4 (database check).
   - Function `app.claim_next_job(stale_seconds)`, `SECURITY DEFINER`, picks the next due job across tenants
     with `FOR UPDATE SKIP LOCKED`. It follows the pattern of `app.resolve_membership`: the worker has no
     tenant context until it holds a job. A job left `running` by a crashed worker is taken again after the
     stale delay.
2. **`avenel/jobs/queue.py`** — enqueue (no-op when an active job exists), claim, succeed, fail with backoff
   and jitter, and after the fourth failed attempt: job `failed` plus a blocking `INTEGRATION_FAILURE` issue
   (code already in the pack).
3. **`avenel/jobs/worker.py`** — real loop. For each job: set the tenant RLS context, run the handler and mark
   the job `succeeded` **in the same transaction** as the handler's writes.
4. **First use** — when `complete-upload` hits `OcrUnavailableError`, it queues a `read_document` job, sets the
   document to `processing` and answers **202** instead of 503. The worker retries the reading.
   The normal path (OCR available) is unchanged: still read inside the request, still 200.

## Not in step 1

- Moving the normal reading path to the queue (API would answer 202 for every upload, the file screen would
  poll). Step 2, after step 1 has run on the real stack.
- `avenel.workflow.transition()` enqueuing the next job (D.1). Step 3.
- A separate database role for the worker. Today the worker uses `avenel_app`, which may execute
  `app.claim_next_job`. Recorded in TECHNICAL_DEBT.

## Values chosen (engineering constants, not legal values)

| Constant | Value | Why |
|---|---|---|
| Max attempts | 4 | ARCHITECTURE.md D.1 |
| Backoff | 30 s × 2^(attempt−1), plus up to 100 % random jitter | D.1 asks for exponential backoff with jitter; the base is our choice |
| Stale `running` job | 15 minutes | Longer than any document reading seen so far |
| Poll interval when idle | 5 seconds | |

## Tests

Queue: enqueue is idempotent; only one worker gets a job (two concurrent claims); retry sets `run_after` in
the future and the job is not claimable before it; fourth failure marks `failed` and opens one
`INTEGRATION_FAILURE` issue; a stale `running` job is reclaimed; `attempts` cannot pass 4; `avenel_app` under
RLS cannot see another tenant's jobs. Worker: a job succeeds and its writes commit together; a failing
handler leaves no partial write. API: OCR down → 202, job queued, document `processing`; then the worker,
with OCR back, reads the document.

## Exit

All of the above pass with the full suite, lint and type checks. Real-stack proof (Docker worker picking a
job after the OCR container is stopped and restarted) is a separate, stated step.
