# Phase 8d plan — Cancelling a monthly file (18 November 2026)

Asked by the founder on 18 November 2026 ("continue building"). Spec: ARCHITECTURE.md D.1 ("Any non-terminal
state ──cancel──> cancelled") and the API list in Part C (`POST /work-requests/{id}:cancel`).
Follows phase 8c, whose report lists cancel, timeouts and `failed` as not built.

## In scope

| Piece | What it does |
|---|---|
| `avenel/workflow/cancel.py` | `cancel()`: moves the file to `cancelled` through `transition()` with the reason, cancels a pending approval and the file's queued jobs, all in one transaction. |
| Migration 018 | Jobs may end as `cancelled` (finished, never run). New migration; 001–017 untouched. |
| Worker and orchestrator | A job of a cancelled or failed file is not run: it ends as `cancelled`. A job already running when the file is cancelled finishes its own step but hands nothing on (no next job, no status change). |
| API | `POST /v1/work-requests/{id}:cancel` with `{reason}`. Owner and manager only (403 for others, 404 for a client user or another firm). 409 when the file is already finished or cancelled. In the contract. Uploads into a cancelled or failed file answer 409. |
| Client portal | Requests waiting on the client for a cancelled file are no longer listed, and answering one is refused (it stays `waiting_client` in the record). |
| Screen | "Annuler le dossier" on the monthly file for owners and managers, with a required reason and a confirmation. The status and the history show the cancel and its reason. Uploading is hidden on a cancelled file. |
| Tests | Python (service, worker, API, roles, tenancy) and a browser test on the real stack. |

After a cancel, a new monthly file can be opened for the same period: the database already allows one active
file per period and does not count cancelled ones (`work_requests_one_active_per_period`).

## Interpretation (to confirm)

- **Who may cancel:** owner and manager. B.2 gives the firm manager "assign work, manage clients and periods";
  accountants and staff are not given it. Easy to widen.
- **What is kept:** documents, readings, proposals, issues and the audit trail stay as they are (evidence is
  never deleted). The file is only closed.

## Not in this phase

- **Timeouts that escalate to the firm manager** (D.1). The spec gives no duration. Needs a decision: how long
  a file may wait on a client, and on an approver, before the manager is told, and how they are told (in the
  app only, or by email once a provider is chosen).
- **`failed`:** D.1 allows "any state ──unrecoverable──> failed" but does not say what is unrecoverable. Jobs
  that run out of attempts already raise an `integration` issue (D.1 rule). Not built until a real case needs it.
