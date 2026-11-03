# Phase 5c-1 — Separation, real auth, honest CI

Status: **draft, awaiting human approval.** No code changed yet. This file is the only write to the fiscai repo in this phase (plus nothing else — all work happens in `../avenel-split`).

## 0. Facts observed while planning (not taken from earlier reports)

| # | Observation | Source |
|---|---|---|
| F1 | `42191be` is the **root commit** (`git rev-list --max-parents=0 HEAD`). "History from 42191be onward" = all 32 commits. FiscAI history before it is not in git. | git |
| F2 | `git filter-repo` is **not installed**. `make` is **not installed** (only `make.cmd` / `make.ps1` shims). Docker 28.1 + Compose 2.35 are present. | shell |
| F3 | `docker-compose.yml` (dev) has postgres, minio, keycloak, clamav, freshclam, ocr. It has **no `api` and no `worker` service**. Keycloak runs `start-dev` with **no realm import** (no `--import-realm`, no volume). | docker-compose.yml |
| F4 | `realm-export-test.json`: realm `avenel`, OTP policy `totp`, client `avenel-web` public, redirect URIs `localhost:3000/*` and `localhost:8080/*` (8080 is Keycloak itself), **no PKCE attribute**, one user `ci-accountant@test.internal` with an OTP credential (test secret present in the export). | realm file |
| F5 | **Auth bypass in `apps/api/deps.py:43-131`.** If the bearer token is not a 3-part JWT, the raw token string is used as the OIDC subject; `X-Identity-Subject` alone also authenticates. In that path `X-Auth-Time` and `X-MFA-Authenticated` are read from client headers and **MFA defaults to `true`, auth_time to now**. There is no environment gate. Any caller who knows a user's subject can act as them and pass the approval step-up check. | code |
| F6 | `GET /v1/work-requests` exists (`listWorkRequests`, contract line 402; route `apps/api/routes/work_requests.py:68`). | code |
| F7 | `tailwind.config.js` uses `theme.extend.colors` (default palette still present) and adds a FiscAI `brand` scale. No `@font-face` in `src/index.css`. Fonts exist in `public/fonts/`. | code |
| F8 | `apps/web/` is an abandoned Next.js draft. `src/` is mostly FiscAI; AVENEL screens live in `src/components/domain/{Queue,ProposalReview,DocumentViewer,Reconciliation,Approval,Export,PortalRequests,InternalMetrics}Screen*.tsx`. | tree |
| F9 | `tests/.test_count_baseline` + `scripts/check_test_count.py` (min 107) guard pytest count only. | code |

## 1. Decisions I need from you before executing

1. **F5 auth bypass (backend change).** Proposal: gate the subject-header / plain-token path and the `X-Auth-Time`/`X-MFA-Authenticated` overrides behind `AVENEL_AUTH_TEST_MODE=1`, set only by `tests/conftest.py`; in every other environment a non-JWT token returns 401 and MFA/auth_time come only from verified JWT claims (`acr`/`amr`, `auth_time`). Add tests: (a) without the flag, `X-Identity-Subject` → 401; (b) without the flag, plain token → 401; (c) JWT without fresh `auth_time` → 401 `insufficient_user_authentication` on decide. No existing assertion about tenancy/approval is weakened; existing tests keep running under the flag. **DECIDED (human, 2026-11-03): gate it.** The real-stack e2e cannot honestly prove auth while this bypass exists.
2. **Tooling install (DECIDED: install both):** `pip install git-filter-repo` and GNU make (`choco install make`, needs admin) — or I make `make ci` work via the existing `make.cmd` shim. Which?
3. **Ports (DECIDED: 5173/8080/8000):** SPA served by Nginx on `5173` in compose (Keycloak keeps `8080`, API `8000`). OK?

## 2. Execution steps

### Step 1 — New repository
- `git clone --no-local fiscai ../avenel-split` (fresh clone, origin then removed).
- `git filter-repo --paths-from-file keep.txt` with an allow-list: `avenel/ apps/api/ db/ jurisdiction/ contracts/ tests/ fixtures/ scripts/ docker/ infra/ docs/ e2e/ src/ public/ index.html package.json package-lock.json vite.config.ts tsconfig*.json postcss.config.js tailwind.config.js playwright.config.ts Makefile requirements.txt pytest.ini docker-compose*.yml .github/ .spectral.yaml ARCHITECTURE.md STRATEGY.md AGENTS.md CLAUDE.md`. Excluded: `fintech-research/`, `apps/web/`, `.claude/`, `storage_data/`, `dist/`, reports, zip pack, `make.*` shims (pending decision 2).
- `src/` is mixed, so it is kept by path then cleaned in step 2 (history will still contain old FiscAI `src/` blobs — I will state that; rewriting per-file is possible with a second pass if you want history fully clean).
- No remote added. fiscai is never written, rewritten or pushed. **Ask before pushing to github.com/eliem08/avenel.**
- Check: `git -C ../avenel-split log --oneline | head`, `git -C ../fiscai status` unchanged.

### Step 2 — Remove FiscAI code
- Delete: `src/pages/*` (all), `src/services/*`, `src/lib/{alertRules,checklist,extraction,riskScoring,sqlGuard,validation,report,sanitize}*`, `src/mocks/`, `src/store/authStore.ts`, FiscAI i18n catalog, FiscAI components (`AgentCard, AlertCard, ChecklistView, Disclaimer, DossierCard, KpiCard, ReportPreview, RiskBadge, SeverityBadge, UploadZone, components.test.tsx`), `src/components/layout/*` (replaced in step 6), `e2e/journey*.spec.ts`, `e2e/pilot-journey.spec.ts`, `e2e/document-viewer.spec.ts`, `e2e/accessibility.spec.ts` (re-added against real routes later phase), `apps/web/`, `PilotDemoPage`, `/pilot`, `/viewer`.
- AVENEL screen components without a live data source this phase (Review, Reconciliation, Approval, Export, Portal, Metrics) are **kept as components but not routed**; their default mock props are removed so guard 25 holds. Their unit tests stay if they pass props explicitly.
- `TESTS_REMOVED.md`: every removed test file with test count and reason; then a new Vitest baseline file + guard (same pattern as pytest baseline). Pytest baseline unchanged (no backend test removed).
- `package.json` name/description → `avenel-web`.
- Check: `grep -ri` for the 9 FiscAI terms, `npm test`, `npm run build`.

### Step 3 — ADR-002 + ARCHITECTURE.md
- `docs/adr/ADR-002-frontend-location.md`: the console is the Vite SPA at repo-root `src/` (build → Nginx); `apps/web` removed.
- ARCHITECTURE.md: edit only C.2 "Web" row if needed and C.3 layout (`/src` Vite console, no `/apps/web` Next.js). Add Part K 25–28 in step 7. Nothing else; `git diff ARCHITECTURE.md` shown.

### Step 4 — Design system
- `src/styles/fonts.css`: `@font-face` for Readex Pro 600, IBM Plex Sans 400/500/600, IBM Plex Sans Arabic 400/600 from `/fonts/*.woff2`, `font-display: swap`. Verify each referenced file exists.
- `tailwind.config.js`: `theme.colors` (override) = Part E tokens + `transparent` and `current` only (needed for borders/SVG; I will list them in the ADR — tell me if you want even those excluded). Remove `brand`.
- `scripts/check_css_palette.mjs`: builds, scans `dist/assets/*.css` for `(bg|text|border|ring|fill|stroke|from|to|via|divide|outline|placeholder)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|blue|indigo|violet|purple|fuchsia|rose|white|black)` and default hex values; also a Vitest test calling it. Wired into `make ci`.

### Step 5 — Real browser auth
- `oidc-client-ts` `UserManager` with `response_type=code`, PKCE S256, `InMemoryWebStorage` for `userStore` **and** `stateStore` (no localStorage/sessionStorage; a test asserts both are untouched after login).
- Silent refresh via refresh token (`automaticSilentRenew`); logout via `signoutRedirect` to `/`.
- Step-up: `requireFreshMfa()` → `signinRedirect({ prompt: 'login', max_age: 300, acr_values: 'mfa' })`, then the app checks `auth_time` ≤ 300 s and `amr` contains otp before calling approval. Realm: add PKCE S256 to `avenel-web`, redirect URI for the SPA port, browser flow requiring OTP for the test user, `acr`/`amr` mappers. Prod realm gets the same client changes (shown in diff).
- Routes: `/` = AVENEL login screen (button "Se connecter"), `/callback`, everything else under `<RequireAuth>`.
- Compose: Keycloak `start-dev --import-realm` with the test realm mounted.

### Step 6 — App shell + Queue
- `Rail` (220px): firm switcher (memberships from API session endpoint if present — otherwise single firm from token, **stated as such**), Queue, Clients, Approvals, Settings. French copy per E.8. Clients/Approvals/Settings render an EmptyState saying the screen arrives in a later phase (no fake data).
- `openapi-typescript` + `openapi-fetch` generate `src/api/schema.d.ts` from `contracts/openapi.yaml` (`npm run gen:api`, CI fails if regenerated output differs).
- Queue: `GET /v1/work-requests` with bearer token + `X-Tenant-Id`; loading, empty ("Aucun dossier pour …"), error ("Le serveur ne répond pas. Réessayez dans un instant.") states. Error state is exercised in e2e by stopping the `api` container.

### Step 7 — CI guards (Part K 25–28)
- 25 `scripts/guards/no_test_code_in_prod.mjs`: AST/regex over `src/**` excluding `*.test.*`, fails on imports from `tests/`, `fixtures/`, `e2e/`, or module/identifier names matching `^(mock|fixture|fake)`; then scans `dist/` for the same.
- 26 `scripts/guards/no_e2e_interception.mjs`: fails on `page.route`, `context.route`, `route.fulfill`, `routeFromHAR`, `setOffline`… in `e2e/**`.
- 27 `scripts/guards/no_fiscai_terms.mjs`: case-insensitive list from the brief over tracked source (excluding `docs/reports/`, `TESTS_REMOVED.md`, the guard file itself, ARCHITECTURE history?) and `dist/`. **Exclusion list will be shown to you.**
- 28 `make e2e`: `docker compose up -d --build --wait`, then polls `GET /v1/health` (and Keycloak `/health/ready`); fails before Playwright if not green.
- Compose gains `api`, `worker`, `web` services (reusing `Dockerfile.api`, `Dockerfile.web`) and a one-shot `seed` service.
- Each guard has a self-test with a planted violation. Makefile `ci` = existing targets + `guards css-check web-test web-build e2e`. `.github/workflows/ci.yml` mirrors it.
- Part K 25–28 appended to ARCHITECTURE.md.

### Step 8 — E2E against the real stack
- `e2e/login-queue.spec.ts`: open `/`, click "Se connecter", Keycloak form, username/password from the test realm, TOTP computed with `otpauth` from the realm's test secret, land on Queue, see the seeded work request rows, log out, back on `/`.
- Second assertion: with the token obtained in the browser, call the API session endpoint and compare tenant id to the seed's tenant id.
- Proof of real traffic: Playwright logs every request to `:8000` (`page.on('request')`, observation only, no interception) **and** the API container log for the same window is saved to `docs/reports/phase-5c-1-e2e-api.log`.
- Seed: `scripts/seed_e2e.py` inserts one tenant, one membership for the Keycloak user's `sub` (fixed id in the realm export), two client entities, periods, work requests. Seed data is synthetic and contains no tax values.

### Step 9 — Corrections report
- `docs/reports/phase-5b-corrections.md`: each earlier claim relying on the mocked frontend (from audit-2 §3.4 and phase reports), what was true, what is true now.
- `docs/pilot/go-live-checklist.md`: update any item that cited the mocked e2e.

### Exit
- `make ci` green in `../avenel-split`, including e2e job; screenshots (login, Keycloak OTP prompt, Queue) via Playwright `screenshot()`.
- `docs/reports/phase-5c-1-report.md` with: changes by item, raw `make ci` output, e2e log with API requests, clean-machine reproduce commands, Unverified, Stubbed.
- New `CLAUDE.md` with your exact text. Stop; no Phase 5c-2.

## 3. Known risks / likely "Unverified" items
- GitHub Actions run of the docker-compose job (only run locally until pushed).
- ClamAV image needs signatures (freshclam, ~1–3 min, network) before healthy.
- OCR container healthcheck is a placeholder HTTP server; I will state what it is.
- Step-up re-auth flow is exercised in e2e only as far as the approval button exists; there is no approval screen wired this phase, so the step-up path is tested at the auth-module level and stated as such.
- Windows host: the clean-machine commands will be given for Linux/macOS bash and verified here on Windows Git Bash only.
