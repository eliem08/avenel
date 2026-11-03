# Tests removed — Phase 5c-1 (repository split)

Counts are `it(`/`test(` declarations found by grep in each file at fiscai `af7e1b5`. Runtime counts can be higher where a test uses `.each` (audit-2 reported 161 Vitest tests at runtime).

No pytest test was removed. The pytest baseline (`tests/.test_count_baseline` = 214) is unchanged.

## FiscAI PreClear tests (product removed from this repository)

| File | Declarations | Reason |
|---|---|---|
| src/services/services.test.ts | 19 | FiscAI auth/dossier/document services on the localStorage db |
| src/components/domain/components.test.tsx | 11 | FiscAI components (RiskBadge, DossierCard, …) |
| src/pages/pages.test.tsx | 14 | FiscAI pages (landing, login, dossiers) |
| src/lib/riskScoring.test.ts | 13 | FiscAI risk score |
| src/lib/sqlGuard.test.ts | 5 | FiscAI NLU query filter |
| src/services/aiAnalysisService.test.ts | 12 | FiscAI 7-agent pipeline (mocked) |
| src/lib/validation.test.ts | 11 | FiscAI form validation |
| src/lib/checklist.test.ts | 7 | FiscAI import/export checklist |
| src/lib/extraction.test.ts | 7 | FiscAI mocked extraction |
| src/i18n/i18n.test.ts | 6 | FiscAI catalog |
| src/lib/alertRules.test.ts | 5 | FiscAI alerts |
| src/lib/sanitize.test.ts | 5 | FiscAI sanitizer (module removed) |
| src/services/reportService.test.ts | 5 | FiscAI reports |
| src/components/ui/ui.test.tsx | 7 | FiscAI-styled primitives depending on the localStorage db; replaced by Part E primitives |
| e2e/journey1-import-analysis.spec.ts | 1 | FiscAI journey |
| e2e/journey2-expert-review.spec.ts | 1 | FiscAI journey |
| e2e/journey3-alerts.spec.ts | 1 | FiscAI journey |
| e2e/journey4-navigation.spec.ts | 3 | FiscAI journey |
| e2e/journey5-validation-errors.spec.ts | 2 | FiscAI journey |

## AVENEL tests removed because they only exercised mocks

| File | Declarations | Reason |
|---|---|---|
| e2e/pilot-journey.spec.ts | 1 | Ran against static `/pilot` mocks with no backend; the "TOTP" step typed a constant (audit-2 §3.3). Replaced by `e2e/login-queue.spec.ts` against the docker-compose stack. |
| e2e/accessibility.spec.ts | 1 (loops over 7 screens) | Scanned `/pilot` mock screens only. To be re-added against real routes when those screens are wired (Phase 5c-2). |
| e2e/document-viewer.spec.ts | 2 | Ran on `/viewer` with static data. Same as above. |

## Baseline reset

After removal, the Vitest suite is the 3 AVENEL component files (22 tests at runtime). The new baseline is recorded in `src/.test_count_baseline` and enforced by `scripts/guards/check_web_test_count.mjs` (see Makefile `web-test`).
