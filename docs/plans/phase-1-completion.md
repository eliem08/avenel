# Phase 1 completion — tenancy, clients, periods, through the real stack

Status: in progress (human instruction 5 Nov 2026: "do the first phases first, phase by phase"). Stops for review at the exit criteria below.

## Where Phase 1 stood (checked 5 Nov 2026)

- Backend endpoints and tests exist for every Phase 1 item; `tests/api/test_phase1_matrix.py` covers every Phase 1 endpoint in four quadrants.
- **But** API tests ran as a Postgres superuser, so RLS (the second tenancy layer, Part A.4) was never exercised through the API. Running them as `avenel_app` exposed two production bugs (no DELETE on `issues`, no grant on `export_round_trips`). Fixed in migration 010 with a supersede rule (human decision), plus a privilege guard test. Done in `ed2ec1a`.
- Browser: only login and the Queue exist (Phase 5c-1). No screen for clients, periods, chart of accounts, or the DPA/CNDP documents.
- Chart import: Part G says CSV/XLSX. The hardened parsers exist (`avenel/accounting/chart_import.py`, zip-bomb/XXE checks) but the API only accepts already-parsed JSON rows.

## Work

1. **API: file chart import.** `POST /client-entities/{id}/chart-accounts/import-file` (multipart, one file, `.csv` or `.xlsx`, size limit from the parser) calling the existing `parse_csv_chart` / `parse_xlsx_chart`, then the existing `import_chart_accounts`. Same scope-first 404 / role 403 rules as the JSON import. Contract updated; added to the Phase 1 matrix test and the cross-tenant test.
2. **Clients screen** (`/clients`): table (Société, ICE, IF, État), "Nouvelle société" form (raison sociale, ICE, IF; server validation messages shown as returned), edit, archive with a confirmation dialog. Read-only for roles the API refuses.
3. **Client page** (`/clients/:id`): Périodes (list; "Ouvrir une période": code YYYY-MM, start/end computed from the code, fiscal year end entered by the user, never defaulted; overlap error shown as returned by the API), Plan comptable (list; "Charger le plan CGNC"; file import).
4. **Settings → Conformité** (`/settings`): DPA draft and CNDP dossier rendered from the API, with the "projet à valider par un juriste" notice and the `needs_expert` dependencies listed.
5. **Seed/realm:** second Keycloak test user `client_user` scoped to one of the two seeded companies (OTP).
6. **E2E (real stack, no interception):** accountant creates a company, opens a period, gets the overlap error on a second overlapping period, seeds CGNC, imports a CSV file, reads the DPA. Client user logs in and sees only the scoped company (Queue and Clients). Every API request logged.
7. **Report:** `docs/reports/phase-1-completion-report.md` (raw `make ci`, API request log, screenshots, Unverified, Stubbed). Stop.

## Exit criteria (Part G Phase 1 + 5c-1 rules)

- Cross-tenant tests for every Phase 1 endpoint return 404, **with the API connected as `avenel_app`**.
- Client user cannot see another company: API test **and** browser e2e.
- Audit chain verifies (`make audit-verify`).
- Every Phase 1 capability is usable in the browser against the real stack, shown in the e2e request log.
- `make ci` green locally; CI green on GitHub once pushed with your go-ahead.

## Not in Phase 1

Expert sign-off of jurisdiction rules (Part I), DPA/CNDP legal validation by a lawyer, real CNDP filing.
