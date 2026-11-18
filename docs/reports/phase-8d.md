# Phase 8d report — Cancelling a monthly file (18 November 2026)

Asked by the founder on 18 November 2026 ("continue building"). Spec: ARCHITECTURE.md D.1 ("any non-terminal
state ──cancel──> cancelled") and Part C (`POST /work-requests/{id}:cancel`). Plan: `docs/plans/phase-8d-cancel.md`.

## What was built

- **`avenel/workflow/cancel.py`:** `cancel()` moves the file to `cancelled` through the state machine, with the
  reason in its history. In the same transaction:
  - a pending approval is closed, recording who closed it, when and why;
  - the file's queued jobs end as `cancelled`.
  Documents, readings, proposals, issues and the audit trail are kept.
- **Migration 018:** jobs may end as `cancelled`. Migrations 001–017 are untouched; 018 is pinned in the hash
  check and its rollback is covered by the migration round-trip test.
- **Worker and agents:**
  - A job of a cancelled file is not run; it ends as `cancelled`.
  - A step already running when the file is cancelled keeps its own work but hands nothing on: no next job, no
    status change.
- **API:**
  - `POST /v1/work-requests/{id}:cancel` with a required reason, in the contract and the typed client.
  - Firm owner and manager only: 403 for accountants and staff; 404 for a client user or another firm.
  - 409 when the file is already finished or cancelled.
  - Uploads into a cancelled file answer 409.
  - A new file can be opened for the period after a cancel. The API used to refuse this whenever any file
    existed for the period, cancelled or not, although the database allowed it; fixed.
- **Client portal:** requests waiting on the client for a cancelled file are no longer listed, and answering one
  is refused.
- **Screen:**
  - "Annuler le dossier" on the monthly file, for owners and managers, with a required reason and a
    confirmation step.
  - A cancelled file says so, hides uploading and the approval request, and shows the cancel and its reason in
    "Historique du dossier".
  - Screenshot: `docs/reports/phase-8d/01-file-cancelled.png`.
- **Test user:** a firm manager, `ci-manager@test.internal`, in the test login realm and the e2e seed. The
  seed adds it to stacks seeded earlier too.

## Interpretation (to confirm)

- **Who may cancel:** owner and manager. B.2 gives the manager "assign work, manage clients and periods".
- **Separation of duties covers closing an approval:** a manager who requested the approval cannot cancel the
  file while that approval is pending (409, "un autre responsable du cabinet doit l'annuler"), unless the firm
  allows one-person approval. This follows the existing database rule on approvals; nothing was loosened.

## Found while building

1. **My first version broke a database rule.** Closing the pending approval with only `status = 'cancelled'`
   failed the 001 check: a decided approval must say who, when and why. Caught by the first API test, then
   fixed.
2. **An older bug, not fixed (D-24):** asking for approval a second time while one is pending answers 500, for
   the same reason. It dates from phase 5. The phase 8c report wrongly said this case worked; it is corrected.
   Fixing it changes approval behaviour, so it needs a decision.
3. **The login-queue browser test on CI** expected the queue to call `/v1/client-entities`. Since phase 8c the
   queue gets client names from `/v1/work-requests`, so that call no longer happens. The test now checks the
   work-request call only. This is what failed it on CI after the demo-script fix.

## Proof

- **Python:** 397 tests pass, 7 of them new (`tests/api/test_cancel_api.py`). The run found one failure, the
  migration round-trip test's hard-coded count of 17 migrations; updated to 18 and re-run: passes.
  - The worker test runs a real job through `run_once` on a cancelled file: the handler is never called.
  - The hand-off test runs `after_step` on a cancelled file: no next job is queued and the status stays.
- **Static checks:** ruff, mypy (109 files), migration hashes (001–018), guards (0 violations), Spectral, type
  check, ESLint, 47 web unit tests, production build, and gitleaks on the realm file with the new user.
- **Browser, real stack, no interception:**
  - Phase 8d passes. The manager logged in through Keycloak with a one-time code and cancelled through the
    screen. The API log shows `POST /v1/work-requests/{id}:cancel -> 200`. The history read back through the
    API is `draft>cancelled` with the reason; a second cancel answers 409; a new file for the same period
    answers 201.
  - Phase 3 passes on the rebuilt workers: the agent hand-off is unchanged.
  - Phases 2 and 5 pass (6 tests): uploading and requesting approval on an open file are unchanged, including
    the MFA step-up approval and the Sage export.
  - Login-queue fails locally only on the reused stack's leftover files (64 rows for 2 expected). On CI's clean
    stack it will run after the push.

## Not done (needs a decision)

- **Timeouts that escalate to the firm manager** (D.1): the spec gives no duration and there is no way to tell
  the manager outside the app yet.
- **`failed`:** D.1 does not say what is unrecoverable. Not built until a real case needs it.
- **D-24**, above.
