# Phase 8c report — Work request state machine (18 November 2026)

Asked by the founder on 18 November 2026 ("continue building the saas", then "Finish phase 8c").
Spec: ARCHITECTURE.md D.1. Plan: `docs/plans/phase-8c-workflow.md`.

## What was built

- **State machine** (`avenel/workflow/state.py`):
  - `transition()` is now the only way `work_requests.status` changes.
  - It locks the work request, refuses any edge outside the D.1 graph and checks the edge's guard.
  - It writes the status and a `work_request.status_changed` audit event in the caller's transaction.
  - A rejection sends the file to `preparing` and raises `current_revision`.
- **`advance_to()`** walks `draft → … → quality_check` one guarded edge at a time. It never moves a file
  backwards.
- **No migration:** the 13 statuses already exist in `001_core`, and the history is the append-only, chained
  audit trail.
- **Who moves the file:**
  - **A firm member's completed upload:** `draft → intake → extracting`. A client user's upload does not
    submit the file.
  - **Document agent hand-off:** `→ preparing`.
  - **Bookkeeping agent:** `→ reconciling`, then `→ quality_check`.
  - **Orchestrator:** `→ needs_attention` when blocking issues are open.
  - **Request for approval:** walks to `quality_check` with each guard, then `→ awaiting_approval`.
  - **Rejection:** `→ preparing`, revision + 1.
  - **Export:** `→ exporting → completed / completed_with_open_items`. Exporting an already completed file
    again keeps its status.
- **Agents never approve or export.** The only moves an agent makes are the reading and preparation steps and
  the escalation.
- **API:**
  - `GET /v1/work-requests/{id}/status-history`, for firm staff only. Client users and other firms get 404.
    It is in the OpenAPI contract, and the typed client is regenerated.
  - A refused move answers 409 `avenel/workflow-transition-refused` with a French message, and the
    transaction is rolled back.
- **Screen:**
  - The monthly file shows its status, and a collapsible "Historique du dossier" lists each change with its
    time and who made it (a person, or the agent's name).
  - Screenshot: `docs/reports/phase-3/05-status-history.png`.

## Changes to existing behaviour

- **The approval and export services** no longer write the status themselves; they call `transition()`.
- **A rejection** used to set `needs_attention`. D.1 says `preparing`, as a new revision, and that is what it
  does now. No existing test asserted the old behaviour.
- **Request for approval from a later status:**
  - From `awaiting_approval`, it still works: the previous pending approval is cancelled and the status is
    kept.
  - From any status after approval, such as `completed`, it is refused with a 409.
- **Interpretation of the `extracting → preparing` guard.** D.1 says "every document read, needs_review or
  rejected; none processing". The guard waits for no document in `processing` and no reading job queued or
  running. It does not wait for:
  - bank statements, which are parsed at upload and stay `received` (18 on the dev stack);
  - uploads never completed, which stay `received` with no job;
  - the optional AI help, because the document is already read.

## Found on the real stack and fixed

1. **The document agent could not hand off.** Its own job is still `running` while the handoff runs in the
   same transaction, so the guard counted it as a reading in progress. The file only reached `preparing` one
   step later, under the bookkeeping agent.
   - The fix: the guard ignores the job that is finishing.
   - Regression test: the agent-chain test in `tests/workflow/test_state_machine.py`, now with the job
     `running`. It fails without the fix.
2. **A person was refused for minutes.** The accountant proposed the entry by hand and requested approval
   while the hosted AI was still running on the already-read invoice. The answer was 409 "1 pièce(s) ne sont
   pas encore lues".
   - The fix: the guard no longer waits for AI help. The agents still do.
   - Test: `test_a_person_does_not_wait_for_the_optional_ai_help_but_does_wait_for_a_reading`.
3. **The queue could not find older files by client name.** The queue took client names from
   `/client-entities`, which returns the first 50 clients. With more clients on the stack, older files showed
   "—", and the phase 2 browser test could not find "Riad Menara SARL". This was not caused by the state
   machine; it showed up while re-running the browser tests.
   - The fix: `GET /v1/work-requests` returns `client_legal_name` (added to the contract), and the queue uses it.
   - Test: `test_the_file_list_carries_the_client_name` in `tests/api/test_status_history_api.py`.

## Proof

- **Python:**
  - The full suite passes on the final code: 390 tests in 10 min 45 s, 14 of them new (11 workflow, 3 API).
  - One earlier full run stalled for almost two hours with no database query and no network connection open.
    The filtered output did not show which test. The verbose re-run did not stall. If it happens again, the
    verbose log names the test.
  - Ruff, mypy, the RLS check (36 tables), the audit chain, migration hashes (001–017, unchanged), the
    tax-literal guard and the Spectral contract lint are clean.
- **Frontend:** type check and 47 vitest tests pass. The CSS palette, end-to-end interception and
  legacy-term guards are clean.
  - `no_test_code_in_prod` reports one violation, `avenel/documents/scanner.py: _fixture_mode`. It was
    already there before this phase (D-19), and this phase does not touch it.
- **Browser, real stack, no interception:**
  - Phases 3 and 5 pass: 5 tests, run against the rebuilt api, worker and worker-ai containers.
  - Phase 3 history read through the API:
    `intake(user) > extracting(user) > preparing(agent:document) > reconciling(agent:bookkeeping) >
    quality_check(agent:bookkeeping)`.
  - Phase 5 history through the API, after the MFA step-up approval and the Sage export:
    `intake > extracting > preparing > reconciling > quality_check > awaiting_approval > exporting >
    completed_with_open_items`.
  - The "with open items" ending is correct: the review issues were acknowledged as accepted as is.
  - Phases 2, 3, 4 and 6, after the guard fixes: 6 passed, 1 failed (phase 2, the queue name bug above). After
    the queue fix, phase 2 passes.
  - **Still failing, not caused by this phase:** the login-queue test expects the queue to hold only the
    seeded files (`toHaveCount(seed.clients.length)`). The reused dev stack holds many files left by other
    tests. This is the known leftover-data issue, the same one phase 1 has.

## Not done (needs a decision)

- **A document added after reading has finished** (file in `preparing` or later) is read and proposed by the
  agents, but the status does not go back to `extracting`: D.1 has no such edge.
- **AI help that finishes after a person requested approval** writes a new extraction and runs validation
  again on a file that is already `awaiting_approval`. This already happened before this phase. The approval
  hash covers the proposals, not the extractions, so the approval stays valid.
- **Not built yet:**
  - timeouts that escalate to the firm manager;
  - `cancel` from the screen;
  - `failed` on unrecoverable errors.
