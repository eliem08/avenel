# Phase 5c-2 — one monthly file through the browser, against the real stack

Status: **draft, awaiting human approval.** Nothing in this plan is built yet.

## Goal

Phase 5c-1 proved login and the Queue against the real stack. 5c-2 does the same for the core path of Part E.5, using the API that already exists (no new domain rules):

> open a monthly file → upload a document → see it read (OCR + extraction) → review and correct fields on the document viewer → see the proposed entry → request approval → approve **with MFA step-up (≤ 5 min)** → see the approval recorded.

Reconciliation, export download, client portal and internal metrics move to **5c-3** to keep this phase reviewable. Say so if you want them here.

## Facts this plan relies on (checked 5 Nov 2026)

- Endpoints exist for every step: `POST /work-requests/{id}/uploads`, `POST /documents/{id}:complete-upload`, `GET /documents/{id}`, `/pages/{n}`, `GET|PATCH /documents/{id}/extraction`, `POST /documents/{id}:generate-proposal`, `GET /work-requests/{id}/proposals`, `GET|PUT /proposals/{id}`, `GET /work-requests/{id}/issues`, issue actions, `POST /work-requests/{id}/approvals`, `GET /approvals`, `POST /approvals/{id}:decide`.
- The worker is a sleep loop (5c-1 "Stubbed"). Whether extraction runs inline in the API or needs the worker is **not yet checked**: step 1 below.
- The OCR container is a placeholder `http.server`. The API has a local OCR adapter (RapidOCR/PaddleOCR in-process, per the moved evaluation harness); which one runs in compose is **not yet checked**.
- Segregation of duties (Part K 23): the approver must not be the preparer and must hold a professional registration. The seed has one accountant with no registration, so approval needs a **second seeded user** (`expert_comptable`, registration number, OTP).
- First Linux CI run: login/Queue e2e passed; the API-down e2e failed on TOTP replay (fixed locally in `f1bee69`, not yet pushed).

## Steps

1. **Pipeline reality check (no UI).** Through the API with a real Keycloak token, against compose: upload a synthetic invoice from `tests/fixtures/`, complete upload, poll the document, fetch extraction, generate proposal. Record which steps work, which need the worker and which need real OCR. **If the worker or OCR container must be implemented to get a document read, stop and ask**: that is backend work beyond wiring.
2. **Client and period screens (minimal).** Clients list (`GET /client-entities`) and, per client, periods. "Nouveau dossier" on the Queue (`POST /work-requests`). Only what the flow needs; no chart import UI.
3. **Monthly file screen.** Header (client, period, status, revision), documents list with upload (FileDrop, E.6), issue strip. Upload sends `Idempotency-Key`. Shows intake paused / quarantined states from the API, not invented ones.
4. **Review screen.** Wire the existing `DocumentViewer` and `ProposalReview` components to `/pages/{n}`, `/extraction` (PATCH for "Confirmer") and `/proposals`. Keyboard flow from E.5 stays. Remove any remaining default/sample props so guard 25 holds.
5. **Approval screen with step-up.** Wire `ApprovalScreen`: summary, open issues acknowledged, short subject hash, "Valider le dossier". Before `:decide`, `requireFreshMfa()`; if older than 5 min, re-login with `prompt=login&max_age=300`, return to the screen, then decide. Show 409 `ApprovalStale` and 401 `insufficient_user_authentication` as E.8 errors.
6. **Seed and realm.** Second Keycloak user (approver, OTP) and membership with a synthetic registration number; work request in a state that allows upload. No tax values.
7. **E2E (real stack, no interception).** Accountant uploads, confirms a field, requests approval. The approver logs in, is forced through step-up, approves. Assert through the API (`GET /approvals`, audit chain) and log every API request, as in 5c-1. Add the axe scan back on the real routes (Queue, file, review, approval).
8. **CI.** Push only with your go-ahead; confirm the `e2e-stack` job is green on GitHub.
9. **Report** `docs/reports/phase-5c-2-report.md` in the 5c-1 format (raw `make ci`, API request log, screenshots, Unverified, Stubbed). Stop.

## Open questions for you

1. Keep reconciliation, export, portal and metrics for 5c-3 (recommended), or include them here?
2. If step 1 shows that a document can't be read without implementing the worker job loop or a real OCR container, do you want that built in this phase or stubbed and stated?
3. May I push `f1bee69` (e2e TOTP fix) now so CI confirms 5c-1 on Linux before 5c-2 starts?
