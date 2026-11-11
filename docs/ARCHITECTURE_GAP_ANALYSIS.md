# AVENEL — Architecture gap analysis

**Date:** 11 November 2026. Compares the code with `ARCHITECTURE.md` and with the seven business areas of the
founder's vision. The item-by-item vision table is in `docs/roadmap/vision-gap.md` (7 November 2026) and is
still accurate except where this file says otherwise.

## A. Gaps against ARCHITECTURE.md (the bookkeeping product)

| # | Requirement | What the code does | Risk | Backlog |
|---|---|---|---|---|
| G-1 | D2: every mutating request idempotent; table `idempotency_keys` | **Fixed this cycle.** Was in process memory, not per tenant, replayed before authentication. | Was: double execution on retry, cross-tenant replay. | done (ADR-003) |
| G-2 | C.1 and D.1: one worker process; jobs idempotent by `(work_request_id, step, revision)`, retries with backoff, 4 attempts, then an `integration` issue | Worker is an empty loop. Scan, OCR, classification and extraction run inside the `complete-upload` HTTP request. No retry: an OCR outage returns 503 and the user must retry by hand. | A slow or failed read blocks the request; nothing resumes after a crash. | B-01 |
| G-3 | D.8: classifier and extractor agents behind the provider router | The router enforces residency and logs calls, but no provider client exists. Extraction is OCR plus rules. | Quality gates of Part H cannot be met or measured on real documents. | B-02 (needs a founder decision) |
| G-4 | Part H: gates measured on ≥ 300 labelled real documents per pilot firm | Only synthetic documents. | Accuracy is unknown on real scans, French or Arabic. | B-03 |
| G-5 | Phase 5 exit: round-trip import verified on a pilot firm's Sage and Odoo | Exporters and golden files exist; no real round trip. | Export may be rejected by the firm's software. | B-04 |
| G-6 | Part I: ten items need a Moroccan professional | 42 `needs_expert` markers in the pack; those rules are disabled. | Features depending on them stay off. | B-05 |
| G-7 | A.2 rule 6: never edit an applied migration | The hash guard pinned 001–008 only. **Fixed this cycle:** 009–013 pinned. | Was: an edit to 009–013 would not fail CI. | done |
| G-8 | Part F: object lock on originals | Not enforced by the storage backend (pilot-1 report). | Originals rely on application write-once only. | B-08 |
| G-9 | Part H: Playwright for the full monthly file, axe checks on Queue, Review, Approval | Eight browser test files exist; axe coverage not verified in this audit. | Unknown. | B-09 |

## B. Design weaknesses found in the code

- **One database connection per request, no pool** (`apps/api/deps.py::get_db`). The rate limiter and now the
  idempotency store each open more. Fine for a pilot, a ceiling later. Backlog B-07.
- **Idempotency answer recorded outside the handler's transaction.** See ADR-003 and TECHNICAL_DEBT D-03.
- **`AGENTS.md` says "Version 2.0"** while reports refer to v2.1 conformance. Minor; TECHNICAL_DEBT D-06.

## C. Gaps against the seven business areas

| Area | In the code today | Missing before it can start |
|---|---|---|
| 1. Accounting | The monthly file workflow above, lettrage | G-2 to G-6 |
| 2. Tax intelligence | Versioned pack; legal-source graph (evidence only) | Expert-signed rules; a review workflow for pack updates; RAS rules; daily monitoring job |
| 3. Treasury | Due date is extracted | Payment-term rules (expert), receivables and payables ageing views; payment preparation is excluded by B.3 until the founder changes the scope |
| 4. Financial reporting | Nothing | Full trial balance and opening balances (AVENEL holds one month's proposals, not the books), CGNC statement models confirmed by an expert |
| 5. Management control | Internal review-effort metrics only | Analytical axes on journal lines, budgets; not in ARCHITECTURE.md |
| 6. Public procurement | Nothing; the portal is suspended by the TGR so no source crawl | Applicable public accounting framework and procurement rules validated by experts; not in ARCHITECTURE.md |
| 7. Infrastructure | Internal REST API with an OpenAPI 3.1 contract | Partner authentication, quotas, billing; excluded by B.3 |

Areas 3 to 7 need a scope decision and an ARCHITECTURE.md update before any code (Part A). They are not
started on purpose: the bookkeeping product is not yet proven on real documents.

## D. Security review notes from this audit

- Fixed: cross-tenant and unauthenticated replay of stored answers (G-1).
- Not re-audited in this cycle: JWT verification, RLS policies table by table (`make rls-check` not run),
  rate limiting, secrets handling. Their tests passed; no manual review was done.
