# Phase 8a — Orchestrator and the first three agents

Goal: a monthly file moves from upload to "ready for review" without anyone pressing buttons. Each step is
done by a named agent with its own list of allowed actions. Every handoff is recorded. Anything an agent
cannot settle goes to a person.

This builds on the job queue (B-01, migration 014). It does not add an LLM: the agents are the existing
deterministic services (plus the guarded AI fill already inside document reading), run by the worker.

## Rules kept (Part A, C.4, D.8)
- Agents never approve, export, post or pay. The bookkeeping and reconciliation agents only create
  `proposed` rows, exactly as the buttons did. Approval stays a human action bound to the content hash.
- No tax or legal value is added. Nothing from the unsigned expert pack is used.
- Every agent action runs in the tenant's RLS context, inside the job's transaction.
- `work_requests.status` is not changed by the orchestrator in this phase (the approval and export
  services own their transitions today; the full D.1 state machine is a later step).

## Agents (avenel/workforce/agents.py)
| Agent | Job step | Allowed actions |
|---|---|---|
| document | `read_document` | `document.read` |
| bookkeeping | `prepare_proposals` | `proposal.draft` |
| reconciliation | `reconcile` | `reconciliation.propose` |

A step handler calls `require(agent, action)` before acting; an action outside the list raises and the
job fails into an INTEGRATION_FAILURE issue. A test fails if any agent is ever given `approve`,
`export`, `post` or `pay` actions.

## Handoffs (avenel/workforce/orchestrator.py)
Called by the worker after a step succeeds, in the same transaction:
1. `read_document` done → when no document of the work request is still `received`/`processing`,
   queue `prepare_proposals` for the work request.
2. `prepare_proposals` done → queue `reconcile` if the client has bank transactions, else finish.
3. `reconcile` done → finish.
Finish = if open blocking issues exist, record an **escalated** task (a person must act), else record
**ready_for_review**.

## Migration 015_agent_tasks
- Widens `jobs.step` to `read_document`, `prepare_proposals`, `reconcile`.
- `agent_tasks`: append-only record of each agent run and handoff (agent, step, job, outcome,
  handed_off_from, summary). RLS forced. Granted SELECT, INSERT only.

## API
`GET /v1/work-requests/{id}/agent-tasks` — the timeline of agent work for a work request (read-only,
scoped like the other work-request routes).

## Tests
- Unit/DB: permission guard; handoff chain read → prepare → reconcile; idempotent re-run (no duplicate
  proposals or matches); escalation when a blocking issue is open; RLS on agent_tasks; append-only.
- Real stack: upload one invoice in the browser, see the proposal appear with no click on "proposer",
  and the agent tasks returned by the API.

## Open questions
- Should "escalated" also assign the work request to the firm manager? (Not done here.)
- Client Operations agent (8b) needs an email provider inside the firm's residency policy: decision needed.
