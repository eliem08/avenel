# Phase 8c — Work request state machine (ARCHITECTURE.md D.1)

Goal: `work_requests.status` tells the truth about where a monthly file is, and changes only through one
function that checks the guard, writes the status and an audit event, in the caller's transaction (D.1).

Today the status jumps `draft → awaiting_approval → exporting → completed` through raw `UPDATE`s in the
approval and export services, a rejection sets `needs_attention` (D.1 says `preparing`, new revision), and
nothing records the steps in between, although the agents (phase 8a) now do them.

## Rules kept
- Part A and K: no tax, legal or accounting value is added; no applied migration is edited; no test about
  money, tenancy, approval or immutability is weakened. No migration is needed: the 13 statuses already
  exist in `001_core` and every change is written to `audit_events` (append-only, chained).
- Agents never approve or export (C.4, D.8): the only moves an agent makes are the reading and preparation
  steps and the escalation to `needs_attention`. `awaiting_approval`, `exporting` and the completions stay
  human actions, through the existing approval and export services.

## The graph (exactly D.1)
```
draft → intake → extracting → preparing → reconciling → quality_check
quality_check → needs_attention | awaiting_approval
needs_attention → awaiting_approval
awaiting_approval → exporting | preparing (rejected: current_revision + 1)
exporting → completed | completed_with_open_items
any non-terminal → cancelled ; any → failed
```
`avenel/workflow/state.py`:
- `transition(conn, tenant, wr, to, actor_type, actor_id, reason=None)` locks the work request row, refuses
  an edge that is not in the graph (`TransitionNotAllowed`), checks the guard (`GuardFailed`, French
  message), writes the status (`submitted_at` on intake, `completed_at` on completion) and an audit event
  `work_request.status_changed` with `{from, to, reason}`.
- `advance_to(...)` walks the straight part `draft … quality_check` one edge at a time, each with its guard,
  and stops at the first guard that fails. It never moves a file backwards.

## Guards (D.1 table, plus what each edge needs to be true)
| Edge | Guard |
|---|---|
| draft → intake | period `open`; at least one document or bank statement; caller holds `work.submit` (owner, manager, accountant, staff; not client users, operators or agents) |
| extracting → preparing | no document `processing` and no reading job queued or running (the job finishing in the same transaction excepted). The optional AI help is not waited for: the document is already read (the agents still wait for it before proposing; seen on the stack, a person who proposed by hand was refused for minutes while the hosted AI ran). Bank statements are parsed at upload and stay `received`, and an upload never completed stays `received` with no job: neither is waited for (same rule as the 8a handoff). |
| quality_check → awaiting_approval, needs_attention → awaiting_approval | zero open blocking issues |
| awaiting_approval → exporting | an `approved` approval whose `subject_hash` matches the current proposal set (export service, unchanged) |
| exporting → completed* | export file generated and hashed (export service, unchanged) |

## Who moves the file
| Moment | Move |
|---|---|
| Staff completes an upload | `draft → intake → extracting` |
| Document agent hands off (all read) | `→ preparing` |
| Bookkeeping agent done | `→ reconciling` |
| Reconciliation done, or no bank lines | `→ quality_check`, then `→ needs_attention` if blocking issues are open |
| Accountant requests approval | walks to `quality_check` (guards), then `→ awaiting_approval` |
| Approver rejects | `awaiting_approval → preparing`, revision + 1 |
| Export | `awaiting_approval → exporting → completed / completed_with_open_items` |

Without a worker (reading inside the upload request) the agents do not run; the request for approval walks
the same edges with the same guards, so the history is identical.

## API and screen
- `GET /v1/work-requests/{id}/status-history`: the status changes from the audit trail (staff only, same
  scope rules as agent tasks).
- The monthly file screen shows the history under the status line.

## Tests
- Every edge outside the graph is refused; each guard refuses and then allows; the audit row is written
  in the same transaction (rolled back together).
- A rejected file goes to `preparing` with revision 2 and can be approved again.
- The agent chain moves a file `extracting → preparing → reconciling → quality_check`, and to
  `needs_attention` when a blocking issue is open.
- A client user's upload does not submit the file.
- Real stack: phase 3 and 5 browser tests read the status history through the API.

## Open points (not built here; need a decision)
- A document added after reading finished (file in `preparing` or later) is read and proposed by the agents,
  but the status does not go back to `extracting`: D.1 has no such edge.
- Timeouts escalating to the firm manager (D.1 rules) and `cancel` from the screen are not built.
