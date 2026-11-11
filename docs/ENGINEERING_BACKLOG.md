# AVENEL — Engineering backlog

**Updated:** 11 November 2026. Ordered by value for the bookkeeping product. "Decision" means a human must
choose before work starts (ARCHITECTURE.md A.4).

| # | Item | Why | Size | Blocked by |
|---|---|---|---|---|
| B-01 | **Durable job queue and real worker.** Table of jobs keyed by `(work_request_id, step, revision)`, `FOR UPDATE SKIP LOCKED`, backoff with jitter, 4 attempts, then an `integration` issue (D.1). Move scan, OCR, classification and extraction out of the upload request. | Reading a document should survive a slow OCR, a crash or a restart, and retry by itself. Largest gap against the spec. | Large (new migration 014, worker, API change to "accepted, processing", UI status) | Nothing. Needs a short plan in `docs/plans/` first. |
| B-02 | **Connect one AI provider for classification and extraction** behind the existing router. | Rules alone will not reach the Part H gates on real scans. | Medium | **Decision:** which provider and region, and the CNDP route (Part I item 8). Credentials. |
| B-03 | **Real-document accuracy run.** 300 labelled documents from a pilot firm, field-level report. | No accuracy number exists for real documents. | Medium | Authorised historical files from a pilot firm. |
| B-04 | Sage 100 and Odoo round-trip import on a pilot firm's software. | Phase 5 exit criterion still open. | Small | Access to a pilot firm's Sage or Odoo. |
| B-05 | Expert sign-off session for the 10 items of Part I. | Unlocks disabled pack rules (withholding, deadlines, tolerances). | Small (ours), expert time | A Moroccan professional. |
| B-06 | Acceptance-rate and rework metrics from recorded edits; route the metrics screen. | The business documents' KPIs (acceptance rate, cost per file) are not visible. | Medium | Nothing. |
| B-07 | Database connection pool for the API. | One connection per request plus extra ones for rate limiting and idempotency. | Small | Nothing. |
| B-08 | Object lock or versioned bucket for originals in production storage. | Originals are write-once by application code only. | Small | Hosting choice. |
| B-09 | Run and extend Playwright and axe checks to the full monthly file. | Part H requires it; not verified in the last audit. | Medium | Nothing. |
| B-10 | Finish the legal-source crawl (gazette 1912–1994), report finance-law years found, fix the extraction pattern if early issues word the title differently. | Founder request of 8 November 2026. | Small | The gazette site's availability. |
| B-11 | Review workflow for jurisdiction-pack updates (proposed change, source, reviewer, signature). | Tax rules must never be published unverified. | Medium | B-05 defines who signs. |
| B-12 | Scope decisions for treasury, reporting, management control, public procurement, partner API. | Each needs an ARCHITECTURE.md section before code. | — | **Decision.** |

## Next three priorities

1. **B-01 steps 2 and 3** — prove step 1 on the Docker stack, then move the normal reading path to the queue (upload answers 202, the file screen shows progress) and let workflow transitions queue the next job.
2. **B-02** — AI provider, once the provider and region are decided.
3. **B-03 / B-04** — proof on a pilot firm's real documents and software.

## Done

| Date | Item |
|---|---|
| 11 Nov 2026 | Idempotency keys durable, per tenant, claimed after authentication (ADR-003). |
| 11 Nov 2026 | Migration-hash guard extended to migrations 009–013. |
| 11 Nov 2026 | B-01 step 1: job queue (migration 014), real worker, failed document readings queued and retried. |
