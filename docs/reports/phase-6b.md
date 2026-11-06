# Phase 6b report — Lettrage (7 November 2026)

Scope approved by the founder on 7 November 2026 ("Approve, start 6b"). Spec: ARCHITECTURE.md B.3, D.7b, Part G Phase 6b, Part K 29.

## What was built

- **Migration 011** (`db/migrations/011_lettrage.*`):
  - `lettrage_groups` and `lettrage_allocations`, with forced RLS.
  - `avenel_app` has no DELETE on either table; allocations are append-only.
  - The `lettrage_group_guard` trigger refuses, inside the database:
    - illegal status transitions;
    - deletes;
    - an accepted group that does not balance;
    - an allocation above a line's open balance;
    - lines of unapproved proposals, another account or another counterparty.
  - Applied migrations 001–010 are untouched; the hash check passes.
- **Matcher** (`avenel/lettrage/matcher.py`): pure and deterministic. Candidate kinds:
  - exact;
  - grouped (one payment, several invoices);
  - split (one invoice, several payments or credit notes);
  - partial (only with a shared reference; the larger line keeps an open balance).
  - **No tolerance:** `lettrage.tolerance_mad` and `lettrage.fx_difference_accounts` were added to the pack as `needs_expert` with null values.
- **Service** (`avenel/lettrage/service.py`):
  - open items with aged balances (days overdue from the extracted due date);
  - generate, accept, reject, manual, reverse;
  - letters A, B … Z, AA per account, never reused;
  - every decision is audited.
- **API**: 8 routes in `apps/api/routes/lettrage.py`, in the OpenAPI contract, with a regenerated typed client.
  - Client users: no access (404 out of scope, 403 in scope).
  - Operators: read only.
- **UI**: a Lettrage section on the client page (`src/screens/LettrageSection.tsx`) with:
  - Clients (342) and Fournisseurs (441) tabs;
  - balances per counterparty;
  - proposals to accept or reject;
  - an open-items table with manual selection (enabled only when debit equals credit);
  - accepted letters with Délettrer, which requires a reason.

## Proof

- **Tests:**
  - `tests/lettrage/test_lettrage.py`: 18 tests. Golden cases (instalments, one payment for three invoices, credit note, partial payment and its later settlement), randomised balance checks on the matcher, trigger invariants, grants.
  - `tests/api/test_lettrage_api.py`: 4 tests through HTTP as `avenel_app` (flow, unbalanced manual group 409, other tenant 404, roles).
  - The migration test was updated for migration 011.
- **Real stack:** `e2e/phase6-lettrage.spec.ts`, 4 passing tests against docker compose, no interception. The flow:
  1. The accountant creates the company and its file.
  2. The expert approves the VAT account.
  3. The accountant uploads the real PDF invoice (OCR), proposes the entry, imports the bank statement, reconciles the payment and requests approval.
  4. The expert approves with a fresh MFA login.
  5. On the 4411 account: proposal "Montant identique" for 12 000,00, then accept (letter A), then délettrage with a reason (2 lines reopen), then a manual group and accept (letter B).
- **API request log (browser):**
  - `GET /v1/clients/{id}/open-items?account_class=supplier -> 200`
  - `POST /v1/clients/{id}/lettrage-groups:generate -> 200`
  - `POST /v1/lettrage-groups/{id}:accept -> 200`
  - `POST /v1/lettrage-groups/{id}:reverse -> 200`
  - `POST /v1/clients/{id}/lettrage-groups -> 201`
  - all with `bearer_jwt=true`.
- **Screenshots:** `docs/reports/phase-6b/01-open-items.png` to `04-relettered-B.png`.
- **Local CI:** the `make ci` targets all pass: lint, mypy, openapi-lint, rls-check, audit-verify, pytest (293 tests), web typecheck, Vitest 47/47, css-check and guards. The full Playwright suite was not rerun; the Phase 6b spec was run on its own.

## Not done / open

- **Tolerances and FX settlement differences:** these are expert values. Until they are set, any amount difference is left for manual lettrage of exact amounts.
- **Lettrage across files:** it works on all approved proposals of the client company, across periods. Opening balances (à-nouveaux) from the firm's books are not imported, so items older than AVENEL's first file are not visible.
- **Counterparty names:** the name comes from extraction as `SocieteAtlasFournituresSARL`, because OCR loses the spaces. This existing extraction limitation is visible in the lettrage screen.
- **Lettrage export:** letters are not yet included in the Sage/Odoo export files.
