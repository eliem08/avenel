# Phase 3 completion report — proposals

**Date:** 6 November 2026 · **Repository:** `../avenel-split` (commits after `285e64d`, not pushed)

`make ci` exited **0** locally, including 7 browser tests on the docker-compose stack (1 new for Phase 3). Phase 3 meets its Part G exit criteria with the limits below. Stopped for review; Phase 4 not started.

## Exit criteria

| Criterion | Evidence | Result |
|---|---|---|
| Property tests: every generated proposal balances | `tests/proposals/test_hypothesis_proposals.py` (1 000 examples each), **now fed the extractor's real output shape**; fails on the pre-fix builder | Pass |
| Golden tests for each invoice type | `tests/proposals/test_golden_proposals.py`: purchase, multi-rate, sale, purchase/sales credit notes, fixed asset, non-deductible VAT, auto-entrepreneur, prorata, EUR with residual | Pass (hand-built inputs) |
| Every line has evidence | Builder + new edit rule (an edit without evidence is refused, 422); e2e checks every line's `evidence_refs` has a bbox and **measures** the box on screen | Pass |
| Tax mappings, account suggester, entry builder, FX, probable duplicates, revisions, review screen with keyboard flow | API tests + e2e below | Pass (see limits) |

## Found and fixed

1. **Every document read from a real PDF crashed the entry builder** (`line_items.get` on a list), and the route reported the crash as 422 with the Python message. Builder fixed; the generate and edit routes now return 422 only for input errors and let crashes surface.
2. **The builder ignored the extractor's `tax_breakdown`** (it read `vat_breakdown`/`tax_lines`, and not the `tax_amount` key), so per-rate VAT printed on the invoice was never used; multi-rate VAT would have been computed instead of read. Fixed; the e2e entry has VAT 2 000,00 read from the scan.
3. **No way to create a tax mapping.** Only a test helper wrote them, so every real document ended in `ACCOUNT_UNMAPPED`. New `GET/PUT /v1/client-entities/{id}/tax-mappings` + "Comptes de TVA" on the client page. Per your decision only registered professionals approve; others propose (unapproved, never used); every change is audited.
4. **48 pack rules marked `verified` with no expert signature.** Per your decision they are `source_cited` (enabled, "à confirmer"), listed on the sign-off sheet (`SRC-01..48`); a CI test refuses any `verified` rule without `verified_by`/`verified_at`.
5. **Keycloak tokens carried no MFA proof** (`amr` absent, `acr` "1" even after OTP). Any member with a professional registration was refused by the API, and the 5-minute step-up check could never pass. Test and production realm exports now use a login flow that reports `amr` (`pwd`, `otp`); the e2e shows `amr=["pwd","otp"]`.
6. **Production realm client had no audience mapper**: no production token would have been accepted by the API. Added (unverified on a real production Keycloak).
7. **Edits could save lines with no evidence, or lines with both or neither side** (the latter crashed on a DB constraint). Both are now 422 with a French message.
8. **UI**: evidence box half a line off (fixed frame letterboxed the image; now measured within 1 % in the e2e); "Confirmer la ligne" was dark text on a dark fill and other buttons used `--ok`/`--fail`/`--pink` as fills (my 5c-1 palette mapping). Fixed, with a unit test that fails on the old code.

## Raw output of `make ci`

Full log: `docs/reports/phase-3/make-ci.log` (1173 lines).

<details><summary>make ci — full output</summary>

```
.venv/Scripts/python.exe -m ruff check avenel apps scripts
All checks passed!
.venv/Scripts/python.exe scripts/check_no_tax_literals.py
[LINT PASSED] No forbidden numeric tax literals, hardcoded identifier regexes, or account seeds found in application code.
.venv/Scripts/python.exe scripts/check_migration_hashes.py
SUCCESS: All 16 frozen migrations (001�008) verified intact.
.venv/Scripts/python.exe scripts/check_test_count.py
[TEST COUNT CHECK] Collected: 252 | Required Baseline: 239
[INFO] Updated test count baseline to 252.
[TEST COUNT CHECK PASSED] Test count maintained or increased.
.venv/Scripts/python.exe scripts/generate_expert_sign_off.py --check
PASS: C:\Users\21263\Downloads\avenel-split\docs\pilot\expert-sign-off-sheet.md is up to date with 29 needs_expert rules.
.venv/Scripts/python.exe -m mypy avenel apps/api scripts
Success: no issues found in 89 source files
npx @stoplight/spectral-cli lint contracts/openapi.yaml --ruleset .spectral.yaml
No results with a severity of 'error' found!
.venv/Scripts/python.exe scripts/rls_check.py
Applying migration 001_core from 001_core.up.sql...
Applied 001_core successfully.
Applying migration 002_rls from 002_rls.up.sql...
Applied 002_rls successfully.
Applying migration 003_append_only from 003_append_only.up.sql...
Applied 003_append_only successfully.
Applying migration 004_fx_rates from 004_fx_rates.up.sql...
Applied 004_fx_rates successfully.
Applying migration 005_rounding_directions from 005_rounding_directions.up.sql...
Applied 005_rounding_directions successfully.
Applying migration 006_reconciliation_refinements from 006_reconciliation_refinements.up.sql...
Applied 006_reconciliation_refinements successfully.
Applying migration 007_active_bq_proposal_unique from 007_active_bq_proposal_unique.up.sql...
Applied 007_active_bq_proposal_unique successfully.
Applying migration 008_round_trips_and_approval_policy from 008_round_trips_and_approval_policy.up.sql...
Applied 008_round_trips_and_approval_policy successfully.
Applying migration 009_review_metrics_and_rate_limits from 009_review_metrics_and_rate_limits.up.sql...
Applied 009_review_metrics_and_rate_limits successfully.
Applying migration 010_issue_supersede_and_round_trip_grants from 010_issue_supersede_and_round_trip_grants.up.sql...
Applied 010_issue_supersede_and_round_trip_grants successfully.
Found 31 tables with tenant_id:
  - accounting_periods: rls_enabled=True, rls_forced=True, policies=1
  - agent_runs: rls_enabled=True, rls_forced=True, policies=1
  - approvals: rls_enabled=True, rls_forced=True, policies=1
  - audit_events: rls_enabled=True, rls_forced=True, policies=1
  - bank_accounts: rls_enabled=True, rls_forced=True, policies=1
  - bank_statements: rls_enabled=True, rls_forced=True, policies=1
  - bank_transactions: rls_enabled=True, rls_forced=True, policies=1
  - chart_accounts: rls_enabled=True, rls_forced=True, policies=1
  - client_entities: rls_enabled=True, rls_forced=True, policies=1
  - client_tax_mappings: rls_enabled=True, rls_forced=True, policies=1
  - counterparties: rls_enabled=True, rls_forced=True, policies=1
  - document_versions: rls_enabled=True, rls_forced=True, policies=1
  - documents: rls_enabled=True, rls_forced=True, policies=1
  - evidence_records: rls_enabled=True, rls_forced=True, policies=1
  - export_profiles: rls_enabled=True, rls_forced=True, policies=1
  - export_round_trips: rls_enabled=True, rls_forced=True, policies=1
  - exports: rls_enabled=True, rls_forced=True, policies=1
  - extractions: rls_enabled=True, rls_forced=True, policies=1
  - fx_rates: rls_enabled=True, rls_forced=True, policies=1
  - idempotency_keys: rls_enabled=True, rls_forced=True, policies=1
  - issues: rls_enabled=True, rls_forced=True, policies=1
  - journal_lines: rls_enabled=True, rls_forced=True, policies=1
  - journal_proposals: rls_enabled=True, rls_forced=True, policies=1
  - membership_client_scopes: rls_enabled=True, rls_forced=True, policies=1
  - memberships: rls_enabled=True, rls_forced=True, policies=1
  - provider_calls: rls_enabled=True, rls_forced=True, policies=1
  - reconciliation_match_items: rls_enabled=True, rls_forced=True, policies=1
  - reconciliation_matches: rls_enabled=True, rls_forced=True, policies=1
  - review_effort_metrics: rls_enabled=True, rls_forced=True, policies=1
  - usage_records: rls_enabled=True, rls_forced=True, policies=1
  - work_requests: rls_enabled=True, rls_forced=True, policies=1

[RLS-CHECK PASSED] All 31 tables with tenant_id have forced RLS and tenant policy.
.venv/Scripts/python.exe scripts/verify_audit_chain.py --seed
Applying migration 001_core from 001_core.up.sql...
Applied 001_core successfully.
Applying migration 002_rls from 002_rls.up.sql...
Applied 002_rls successfully.
Applying migration 003_append_only from 003_append_only.up.sql...
Applied 003_append_only successfully.
Applying migration 004_fx_rates from 004_fx_rates.up.sql...
Applied 004_fx_rates successfully.
Applying migration 005_rounding_directions from 005_rounding_directions.up.sql...
Applied 005_rounding_directions successfully.
Applying migration 006_reconciliation_refinements from 006_reconciliation_refinements.up.sql...
Applied 006_reconciliation_refinements successfully.
Applying migration 007_active_bq_proposal_unique from 007_active_bq_proposal_unique.up.sql...
Applied 007_active_bq_proposal_unique successfully.
Applying migration 008_round_trips_and_approval_policy from 008_round_trips_and_approval_policy.up.sql...
Applied 008_round_trips_and_approval_policy successfully.
Applying migration 009_review_metrics_and_rate_limits from 009_review_metrics_and_rate_limits.up.sql...
Applied 009_review_metrics_and_rate_limits successfully.
Applying migration 010_issue_supersede_and_round_trip_grants from 010_issue_supersede_and_round_trip_grants.up.sql...
Applied 010_issue_supersede_and_round_trip_grants successfully.
[AUDIT-VERIFY] Seeded 5 audit events for test tenant 36f1f217-132a-452a-894e-eeb06ee42107
  - Tenant 36f1f217-132a-452a-894e-eeb06ee42107: verified 5 audit events in linear sequence.

[AUDIT-VERIFY PASSED] All 5 audit events across 1 tenant(s) verified linear and intact.
.venv/Scripts/python.exe -m pytest -v tests
C:\Users\21263\Downloads\avenel-split\.venv\Lib\site-packages\pytest_asyncio\plugin.py:300: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the "fixture" caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to "function" scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
============================= test session starts =============================
platform win32 -- Python 3.12.2, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\21263\Downloads\avenel-split\.venv\Scripts\python.exe
cachedir: .pytest_cache
hypothesis profile 'default'
rootdir: C:\Users\21263\Downloads\avenel-split
configfile: pytest.ini
plugins: anyio-4.16.0, hypothesis-6.170.14, platformdirs-4.14.3, asyncio-1.4.1.post1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 251 items

tests/api/test_audit_chain_verifies.py::test_audit_chain_verifies_after_phase1_operations PASSED [  0%]
tests/api/test_auth_jwt.py::test_jwt_valid_signature_authenticates PASSED [  0%]
tests/api/test_auth_jwt.py::test_jwt_expired_token_gets_401 PASSED       [  1%]
tests/api/test_auth_jwt.py::test_jwt_wrong_audience_gets_401 PASSED      [  1%]
tests/api/test_auth_jwt.py::test_jwt_wrong_issuer_gets_401 PASSED        [  1%]
tests/api/test_auth_jwt.py::test_jwt_forged_signature_gets_401 PASSED    [  2%]
tests/api/test_auth_jwt.py::test_jwt_immature_nbf_gets_401 PASSED        [  2%]
tests/api/test_auth_jwt.py::test_mfa_enforced_for_professional_registration PASSED [  3%]
tests/api/test_auth_jwt.py::test_operator_access_lifecycle_and_expiry PASSED [  3%]
tests/api/test_chart_import_file.py::test_import_file_four_quadrants PASSED [  3%]
tests/api/test_chart_import_file.py::test_import_file_xlsx PASSED        [  4%]
tests/api/test_chart_import_file.py::test_import_file_rejects_other_formats PASSED [  4%]
tests/api/test_chart_import_file.py::test_import_file_rejects_corrupt_xlsx PASSED [  5%]
tests/api/test_client_user_scoping.py::test_client_user_cannot_see_unscoped_company PASSED [  5%]
tests/api/test_compliance.py::test_compliance_dpa_and_cndp_generation PASSED [  5%]
tests/api/test_cross_tenant_isolation.py::test_cross_tenant_isolation_every_endpoint_returns_404 PASSED [  6%]
tests/api/test_document_content_upload.py::test_upload_then_process_over_http_only PASSED [  6%]
tests/api/test_document_content_upload.py::test_original_is_write_once PASSED [  7%]
tests/api/test_document_content_upload.py::test_bytes_must_match_declared_size_and_hash PASSED [  7%]
tests/api/test_document_content_upload.py::test_scope_first_404_and_401 PASSED [  7%]
tests/api/test_document_reading_real_pdf.py::test_real_pdf_is_read_with_bboxes[text-pdf] PASSED [  8%]
tests/api/test_document_reading_real_pdf.py::test_real_pdf_is_read_with_bboxes[scanned-pdf] PASSED [  8%]
tests/api/test_document_reading_real_pdf.py::test_page_image_scope_rules PASSED [  9%]
tests/api/test_document_reading_real_pdf.py::test_unrenderable_pdf_fails_loudly PASSED [  9%]
tests/api/test_document_reading_real_pdf.py::test_ocr_engine_unavailable_returns_503 PASSED [  9%]
tests/api/test_documents_intake.py::test_document_intake_full_pipeline_success PASSED [ 10%]
tests/api/test_documents_intake.py::test_exact_duplicate_document_resubmitted_returns_200 PASSED [ 10%]
tests/api/test_documents_intake.py::test_same_file_different_client_entities_creates_two_separate_documents PASSED [ 11%]
tests/api/test_documents_intake.py::test_malware_quarantined_with_immutable_evidence PASSED [ 11%]
tests/api/test_documents_intake.py::test_clamav_stale_or_scanner_down_intake_paused PASSED [ 11%]
tests/api/test_documents_intake.py::test_field_correction_generates_immutable_evidence PASSED [ 12%]
tests/api/test_documents_intake.py::test_scope_first_and_role_permissions PASSED [ 12%]
tests/api/test_health_ready.py::test_health_ready_reports_database_ok PASSED [ 13%]
tests/api/test_health_ready.py::test_health_ready_returns_503_when_database_unreachable PASSED [ 13%]
tests/api/test_idempotency.py::test_missing_idempotency_key_returns_400 PASSED [ 13%]
tests/api/test_idempotency.py::test_idempotent_replay_returns_cached_response PASSED [ 14%]
tests/api/test_idempotency.py::test_same_key_different_body_returns_422 PASSED [ 14%]
tests/api/test_idempotency.py::test_concurrent_in_flight_returns_409 PASSED [ 15%]
tests/api/test_idempotency.py::test_non_mutating_get_does_not_require_idempotency_key PASSED [ 15%]
tests/api/test_periods_and_chart.py::test_periods_overlap_protection_returns_409 PASSED [ 15%]
tests/api/test_periods_and_chart.py::test_chart_accounts_seed_and_import PASSED [ 16%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[get_session-GET-/v1/me-None-200] PASSED [ 16%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[list_client_entities-GET-/v1/client-entities-None-200] PASSED [ 17%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[create_client_entity-POST-/v1/client-entities-payload2-201] PASSED [ 17%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[get_client_entity-GET-/v1/client-entities/{c1_id}-None-200] PASSED [ 17%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[put_client_entity-PUT-/v1/client-entities/{c1_id}-payload4-200] PASSED [ 18%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[patch_client_entity-PATCH-/v1/client-entities/{c1_id}-payload5-200] PASSED [ 18%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[archive_client_entity-POST-/v1/client-entities/{c1_archive_id}/archive-payload6-200] PASSED [ 19%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[list_accounting_periods-GET-/v1/client-entities/{c1_id}/periods-None-200] PASSED [ 19%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[open_accounting_period-POST-/v1/client-entities/{c1_id}/periods-payload8-201] PASSED [ 19%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[list_chart_accounts-GET-/v1/client-entities/{c1_id}/chart-accounts-None-200] PASSED [ 20%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[seed_cgnc_chart-POST-/v1/client-entities/{c1_id}/chart-accounts/seed-cgnc-payload10-200] PASSED [ 20%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[import_chart_accounts-POST-/v1/client-entities/{c1_id}/chart-accounts/import-payload11-200] PASSED [ 21%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[get_dpa-GET-/v1/compliance/dpa-None-200] PASSED [ 21%]
tests/api/test_phase1_matrix.py::test_phase1_matrix_four_quadrants[get_cndp-GET-/v1/compliance/cndp-dossier-None-200] PASSED [ 21%]
tests/api/test_phase5_api.py::test_api_record_round_trip_permissions_and_mfa PASSED [ 22%]
tests/api/test_phase5_api.py::test_api_decide_approval_mfa_5_minute_and_stale_hash PASSED [ 22%]
tests/api/test_phase5_api.py::test_api_issue_acknowledge_endpoint PASSED [ 23%]
tests/api/test_proposal_from_real_document.py::test_generate_on_real_read_document_does_not_crash PASSED [ 23%]
tests/api/test_proposal_from_real_document.py::test_generate_unknown_document_is_404 PASSED [ 23%]
tests/api/test_proposals_api.py::test_proposal_generate_retrieve_and_list PASSED [ 24%]
tests/api/test_proposals_api.py::test_proposal_revision_flow_and_no_per_entry_approval PASSED [ 24%]
tests/api/test_proposals_api.py::test_proposal_role_based_access PASSED  [ 25%]
tests/api/test_review_effort_metrics.py::test_internal_metrics_rbac_owner_and_operator_allowed PASSED [ 25%]
tests/api/test_review_effort_metrics.py::test_no_identifier_values_in_metrics_responses PASSED [ 25%]
tests/api/test_role_action_matrix.py::test_role_action_matrix_create_client PASSED [ 26%]
tests/api/test_role_action_matrix.py::test_role_action_matrix_update_client PASSED [ 26%]
tests/api/test_role_action_matrix.py::test_role_action_matrix_archive_client PASSED [ 27%]
tests/api/test_role_action_matrix.py::test_role_action_matrix_periods PASSED [ 27%]
tests/api/test_role_action_matrix.py::test_role_action_matrix_chart PASSED [ 27%]
tests/api/test_security_headers_and_rate_limits.py::test_security_headers_present_on_all_responses PASSED [ 28%]
tests/api/test_security_headers_and_rate_limits.py::test_rate_limiting_enforced_on_auth_endpoint PASSED [ 28%]
tests/api/test_shared_rate_limiter.py::test_shared_rate_limiter_two_workers PASSED [ 29%]
tests/api/test_tax_mappings_api.py::test_slots_come_from_the_pack PASSED [ 29%]
tests/api/test_tax_mappings_api.py::test_only_registered_professionals_approve PASSED [ 29%]
tests/api/test_tax_mappings_api.py::test_rejects_unknown_slot_and_foreign_account PASSED [ 30%]
tests/api/test_tax_mappings_api.py::test_scope_rules PASSED              [ 30%]
tests/api/test_tax_mappings_api.py::test_unapproved_mapping_is_never_used PASSED [ 31%]
tests/api/test_tax_mappings_api.py::test_real_document_becomes_a_balanced_proposal_with_evidence PASSED [ 31%]
tests/api/test_tax_mappings_api.py::test_edit_keeps_evidence_and_creates_a_revision PASSED [ 31%]
tests/api/test_tax_mappings_api.py::test_edit_without_evidence_is_refused PASSED [ 32%]
tests/api/test_tax_mappings_api.py::test_edit_with_both_sides_is_a_422_not_a_crash PASSED [ 32%]
tests/api/test_tenant_context.py::test_db_spec_function_definitions PASSED [ 33%]
tests/api/test_tenant_context.py::test_no_tenant_context_sees_zero_rows PASSED [ 33%]
tests/api/test_tenant_context.py::test_app_never_runs_query_without_tenant_context PASSED [ 33%]
tests/api/test_tenant_context.py::test_api_unauthenticated_request_refused_before_query PASSED [ 34%]
tests/api/test_xlsx_safety.py::test_xlsx_valid_parse PASSED              [ 34%]
tests/api/test_xlsx_safety.py::test_xlsx_file_size_limit PASSED          [ 35%]
tests/api/test_xlsx_safety.py::test_csv_file_size_limit PASSED           [ 35%]
tests/api/test_xlsx_safety.py::test_xlsx_row_limit PASSED                [ 35%]
tests/api/test_xlsx_safety.py::test_csv_row_limit PASSED                 [ 36%]
tests/api/test_xlsx_safety.py::test_xlsx_zip_bomb_rejection PASSED       [ 36%]
tests/api/test_xlsx_safety.py::test_xlsx_xxe_payload_rejection PASSED    [ 37%]
tests/approvals/test_approvals.py::test_approval_request_refused_on_zero_proposals PASSED [ 37%]
tests/approvals/test_approvals.py::test_approval_request_refused_on_blocking_issues PASSED [ 37%]
tests/approvals/test_approvals.py::test_approval_request_refused_on_unbalanced_proposals PASSED [ 38%]
tests/approvals/test_approvals.py::test_approval_full_flow_segregation_and_registration PASSED [ 38%]
tests/approvals/test_approvals.py::test_unacknowledged_review_issues_blocks_approval PASSED [ 39%]
tests/approvals/test_approvals.py::test_subject_hash_stable_on_approval_status_transition PASSED [ 39%]
tests/approvals/test_approvals.py::test_altering_accepted_match_after_approval_refuses_export PASSED [ 39%]
tests/approvals/test_approvals.py::test_single_person_policy_configured_on_client_entities PASSED [ 40%]
tests/bank/test_bank_statement_parsing.py::test_csv_bank_statement_parsing_valid_balance PASSED [ 40%]
tests/bank/test_bank_statement_parsing.py::test_csv_bank_statement_parsing_balance_break_detected PASSED [ 41%]
tests/bank/test_bank_statement_parsing.py::test_xlsx_bank_statement_parsing PASSED [ 41%]
tests/bank/test_bank_statement_parsing.py::test_ingest_statement_with_balance_break_raises_blocking_issue PASSED [ 41%]
tests/bank/test_bank_statement_parsing.py::test_bank_statement_fixture_stubs_awaiting_real_samples PASSED [ 42%]
tests/bank/test_rib.py::test_moroccan_rib_key_calculation_and_validation PASSED [ 42%]
tests/bank/test_rib.py::test_moroccan_rib_invalid_length_or_characters PASSED [ 43%]
tests/bank/test_rib.py::test_rib_cleaning_and_formatting PASSED          [ 43%]
tests/bank/test_rib.py::test_rib_masking_and_sha256 PASSED               [ 43%]
tests/bank/test_rib.py::test_rib_encryption_roundtrip PASSED             [ 44%]
tests/bank/test_rib.py::test_known_bank_codes_loaded_from_jurisdiction_pack PASSED [ 44%]
tests/bank/test_rib.py::test_app_refuses_to_start_without_rib_encryption_key PASSED [ 45%]
tests/bank/test_rib.py::test_rib_encrypted_never_in_api_response_or_logs PASSED [ 45%]
tests/evaluation/test_synthetic_pipeline.py::test_synthetic_corpus_count_and_report_header_reconciliation PASSED [ 45%]
tests/evaluation/test_synthetic_pipeline.py::test_mixed_inv_002_raises_totals_inconsistent_validator PASSED [ 46%]
tests/evaluation/test_synthetic_pipeline.py::test_synthetic_pipeline_per_field_exact_match PASSED [ 46%]
tests/exports/test_golden_exports.py::test_golden_sage100_csv_byte_identical PASSED [ 47%]
tests/exports/test_golden_exports.py::test_golden_sage100_pnm_byte_identical PASSED [ 47%]
tests/exports/test_golden_exports.py::test_golden_odoo_csv_byte_identical PASSED [ 47%]
tests/exports/test_golden_exports.py::test_evidence_pack_zip_bundle_and_artifacts PASSED [ 48%]
tests/exports/test_golden_exports.py::test_bundle_evidence_pack_zip_with_source_documents PASSED [ 48%]
tests/exports/test_golden_exports.py::test_export_does_not_modify_export_profile PASSED [ 49%]
tests/exports/test_golden_exports.py::test_manual_record_round_trip PASSED [ 49%]
tests/exports/test_golden_exports.py::test_reexport_idempotent_no_double_billing PASSED [ 49%]
tests/exports/test_golden_exports.py::test_download_token_verification_and_expiry PASSED [ 50%]
tests/exports/test_golden_exports.py::test_download_records_audit_event PASSED [ 50%]
tests/guards/test_negative_guards.py::test_tax_literal_linter_fails_on_planted_rate PASSED [ 50%]
tests/guards/test_negative_guards.py::test_linter_fails_on_planted_identifier_regex PASSED [ 51%]
tests/guards/test_negative_guards.py::test_linter_fails_on_planted_account_seed PASSED [ 51%]
tests/guards/test_negative_guards.py::test_spectral_fails_on_planted_nullable_true PASSED [ 52%]
tests/guards/test_negative_guards.py::test_rls_check_fails_on_planted_unprotected_table PASSED [ 52%]
tests/integration/test_keycloak_jwks.py::test_keycloak_real_token_issuance_caching_and_rotation PASSED [ 52%]
tests/integration/test_migrations.py::test_migrations_forward_and_rollback_cycle PASSED [ 53%]
tests/integration/test_migrations.py::test_migrate_down_refuses_in_production PASSED [ 53%]
tests/invariants/test_c4_invariants.py::test_invariant_2_cross_client_composite_fk_rejection PASSED [ 54%]
tests/invariants/test_c4_invariants.py::test_invariant_8_segregation_of_duties_and_registration PASSED [ 54%]
tests/invariants/test_c4_invariants.py::test_invariant_9_overlapping_periods_and_chart_accounts_rejected PASSED [ 54%]
tests/invariants/test_c4_invariants.py::test_unique_nulls_not_distinct_duplicates_rejected PASSED [ 55%]
tests/invariants/test_c4_invariants.py::test_export_fk_requires_approval PASSED [ 55%]
tests/invariants/test_c4_invariants.py::test_invariant_7_export_refused_on_hash_mismatch PASSED [ 56%]
tests/issues/test_issues.py::test_issue_lifecycle_assign_resolve_and_rules PASSED [ 56%]
tests/issues/test_issues.py::test_issue_portal_request_and_client_answer PASSED [ 56%]
tests/issues/test_issues.py::test_acknowledge_review_issue_workflow PASSED [ 57%]
tests/proposals/test_bq_proposal_lifecycle.py::test_bq_proposal_full_lifecycle_and_db_unique_index PASSED [ 57%]
tests/proposals/test_duplicates.py::test_duplicate_window_reads_from_pack PASSED [ 58%]
tests/proposals/test_duplicates.py::test_probable_duplicate_detected_by_exact_invoice_number PASSED [ 58%]
tests/proposals/test_duplicates.py::test_probable_duplicate_detected_by_amount_and_date_window PASSED [ 58%]
tests/proposals/test_duplicates.py::test_negative_monthly_rent_30_days_apart_not_flagged PASSED [ 59%]
tests/proposals/test_duplicates.py::test_negative_two_different_suppliers_same_amount_never_flagged PASSED [ 59%]
tests/proposals/test_duplicates.py::test_record_duplicate_issues_inserts_duplicate_probable PASSED [ 60%]
tests/proposals/test_golden_bank_proposals.py::test_golden_bank_proposal_supplier_payment PASSED [ 60%]
tests/proposals/test_golden_bank_proposals.py::test_golden_bank_proposal_customer_receipt_with_vat_withheld PASSED [ 60%]
tests/proposals/test_golden_bank_proposals.py::test_golden_bank_proposal_bank_fees_and_commissions PASSED [ 61%]
tests/proposals/test_golden_bank_proposals.py::test_bank_fees_missing_mapping_raises_account_unmapped PASSED [ 61%]
tests/proposals/test_golden_bank_proposals.py::test_golden_bank_proposal_unmatched_line_with_suspense_account PASSED [ 62%]
tests/proposals/test_golden_bank_proposals.py::test_golden_bank_proposal_customer_receipt_is_only_withholding PASSED [ 62%]
tests/proposals/test_golden_bank_proposals.py::test_golden_bank_proposal_customer_receipt_combined_withholding PASSED [ 62%]
tests/proposals/test_golden_proposals.py::test_golden_standard_purchase_invoice PASSED [ 63%]
tests/proposals/test_golden_proposals.py::test_golden_multi_rate_purchase_invoice PASSED [ 63%]
tests/proposals/test_golden_proposals.py::test_golden_sales_invoice PASSED [ 64%]
tests/proposals/test_golden_proposals.py::test_golden_purchase_credit_note_reversing_purchase PASSED [ 64%]
tests/proposals/test_golden_proposals.py::test_golden_sales_credit_note PASSED [ 64%]
tests/proposals/test_golden_proposals.py::test_golden_fixed_asset_acquisition PASSED [ 65%]
tests/proposals/test_golden_proposals.py::test_golden_non_deductible_vat_by_cash_limit PASSED [ 65%]
tests/proposals/test_golden_proposals.py::test_golden_non_deductible_vat_by_nature PASSED [ 66%]
tests/proposals/test_golden_proposals.py::test_golden_auto_entrepreneur_supplier_no_vat_lines PASSED [ 66%]
tests/proposals/test_golden_proposals.py::test_golden_prorata_deduction_using_client_entities_vat_prorata PASSED [ 66%]
tests/proposals/test_golden_proposals.py::test_golden_foreign_currency_eur_with_residual PASSED [ 67%]
tests/proposals/test_golden_proposals.py::test_evidence_refs_with_only_rule_refs_rejected PASSED [ 67%]
tests/proposals/test_golden_proposals.py::test_missing_approved_tax_mapping_raises_account_unmapped PASSED [ 68%]
tests/proposals/test_golden_proposals.py::test_missing_fx_rate_raises_fx_rate_missing PASSED [ 68%]
tests/proposals/test_golden_proposals.py::test_golden_foreign_currency_eur_with_negative_residual_credited_to_gain_account PASSED [ 68%]
tests/proposals/test_golden_proposals.py::test_multi_rate_14_percent_accepted_in_2025 PASSED [ 69%]
tests/proposals/test_golden_proposals.py::test_multi_rate_14_percent_rejected_in_2026 PASSED [ 69%]
tests/proposals/test_golden_proposals.py::test_account_suggester_ma_only_without_local_model_falls_back_to_counterparty_history PASSED [ 70%]
tests/proposals/test_golden_proposals.py::test_account_suggester_low_confidence_raises_account_low_confidence_issue PASSED [ 70%]
tests/proposals/test_hypothesis_proposals.py::test_hypothesis_every_proposal_balances_and_has_evidence PASSED [ 70%]
tests/proposals/test_hypothesis_proposals.py::test_hypothesis_every_bank_proposal_balances_and_has_evidence PASSED [ 71%]
tests/reconciliation/test_reconciliation.py::test_reconciliation_exact_single_match PASSED [ 71%]
tests/reconciliation/test_reconciliation.py::test_reconciliation_withheld_vat_match_and_difference_kind PASSED [ 72%]
tests/reconciliation/test_reconciliation.py::test_reconciliation_withheld_vat_unmapped_account_raises_account_unmapped_issue PASSED [ 72%]
tests/reconciliation/test_reconciliation.py::test_reconciliation_no_bank_line_in_two_accepted_matches PASSED [ 72%]
tests/reconciliation/test_reconciliation.py::test_reconciliation_withholding_other_5_pct_is_detected PASSED [ 73%]
tests/reconciliation/test_reconciliation.py::test_reconciliation_combined_withholding_is_and_vat_detected PASSED [ 73%]
tests/rls/test_app_privileges.py::test_avenel_app_role_attributes PASSED [ 74%]
tests/rls/test_app_privileges.py::test_avenel_app_is_not_table_owner PASSED [ 74%]
tests/rls/test_app_privileges.py::test_permission_denied_on_append_only_tables_with_triggers_dropped PASSED [ 74%]
tests/rls/test_app_role_privileges_match_code.py::test_every_write_in_app_code_is_granted_to_avenel_app PASSED [ 75%]
tests/rls/test_app_role_privileges_match_code.py::test_avenel_app_can_select_every_table_it_writes PASSED [ 75%]
tests/rls/test_rls.py::test_make_rls_check_passes PASSED                 [ 76%]
tests/rls/test_rls.py::test_tenant_isolation_and_row_level_security PASSED [ 76%]
tests/rls/test_session_resolution_as_app_role.py::test_resolve_user_session_works_as_avenel_app PASSED [ 76%]
tests/rls/test_session_resolution_as_app_role.py::test_resolve_user_session_as_avenel_app_unknown_subject_is_none PASSED [ 77%]
tests/security/test_auth_test_mode_gate.py::test_subject_header_rejected_outside_test_mode PASSED [ 77%]
tests/security/test_auth_test_mode_gate.py::test_plain_bearer_rejected_outside_test_mode PASSED [ 78%]
tests/security/test_auth_test_mode_gate.py::test_forged_mfa_headers_rejected_outside_test_mode PASSED [ 78%]
tests/security/test_auth_test_mode_gate.py::test_subject_header_still_works_in_test_mode PASSED [ 78%]
tests/security/test_auth_test_mode_gate.py::test_jwt_with_stale_auth_time_cannot_decide_even_with_forged_header PASSED [ 79%]
tests/security/test_production_realm_secrets.py::test_production_realm_export_exists PASSED [ 79%]
tests/security/test_production_realm_secrets.py::test_production_realm_contains_no_static_totp_secret_or_credentials PASSED [ 80%]
tests/security/test_production_realm_secrets.py::test_production_realm_enforces_secure_otp_policy PASSED [ 80%]
tests/security/test_production_realm_secrets.py::test_test_totp_secret_confined_to_ci_test_realm_and_fixtures PASSED [ 80%]
tests/triggers/test_append_only.py::test_audit_events_is_append_only PASSED [ 81%]
tests/triggers/test_append_only.py::test_evidence_records_is_append_only PASSED [ 81%]
tests/triggers/test_append_only.py::test_frozen_proposal_lines_cannot_be_mutated PASSED [ 82%]
tests/triggers/test_append_only.py::test_cannot_move_line_to_another_proposal PASSED [ 82%]
tests/triggers/test_audit_chain.py::test_audit_event_hash_chaining PASSED [ 82%]
tests/triggers/test_audit_chain.py::test_audit_verify_on_seeded_data_passes PASSED [ 83%]
tests/triggers/test_audit_chain.py::test_audit_verify_detects_tampering_and_exits_non_zero PASSED [ 83%]
tests/triggers/test_audit_concurrent.py::test_concurrent_audit_inserts_chain_stays_linear PASSED [ 84%]
tests/triggers/test_balance_trigger.py::test_balanced_proposal_commits_successfully PASSED [ 84%]
tests/triggers/test_balance_trigger.py::test_unbalanced_proposal_fails_on_commit PASSED [ 84%]
tests/triggers/test_balance_trigger.py::test_proposal_with_single_line_fails_on_commit PASSED [ 85%]
tests/triggers/test_balance_trigger.py::test_line_with_both_debit_and_credit_rejected PASSED [ 85%]
tests/triggers/test_document_versions_malware_scan.py::test_malware_scan_column_removed_from_document_versions PASSED [ 86%]
tests/triggers/test_document_versions_malware_scan.py::test_document_versions_current_view_reflects_evidence_records PASSED [ 86%]
tests/unit/test_deterministic_validation.py::test_validation_all_clean_purchase_invoice PASSED [ 86%]
tests/unit/test_deterministic_validation.py::test_validation_missing_mandatory_purchase_mention PASSED [ 87%]
tests/unit/test_deterministic_validation.py::test_validation_arithmetic_inconsistency_blocks PASSED [ 87%]
tests/unit/test_deterministic_validation.py::test_validation_unknown_vat_rate_blocks PASSED [ 88%]
tests/unit/test_deterministic_validation.py::test_validation_auto_entrepreneur_charging_vat PASSED [ 88%]
tests/unit/test_deterministic_validation.py::test_validation_cash_limit_exceeded PASSED [ 88%]
tests/unit/test_deterministic_validation.py::test_validation_period_mismatch PASSED [ 89%]
tests/unit/test_hashing.py::test_canonical_json_formatting PASSED        [ 89%]
tests/unit/test_hashing.py::test_proposal_set_hash_determinism PASSED    [ 90%]
tests/unit/test_jurisdiction_pack.py::test_jurisdiction_pack_schema_validation PASSED [ 90%]
tests/unit/test_jurisdiction_pack.py::test_part_i_items_present_and_needs_expert PASSED [ 90%]
tests/unit/test_jurisdiction_pack.py::test_every_rule_has_non_empty_source PASSED [ 91%]
tests/unit/test_pack_verified_requires_signature.py::test_every_verified_rule_names_who_verified_it_and_when PASSED [ 91%]
tests/unit/test_pack_verified_requires_signature.py::test_planted_unsigned_verified_rule_is_caught PASSED [ 92%]
tests/unit/test_residency_router.py::test_residency_policy_region_allowlist PASSED [ 92%]
tests/unit/test_residency_router.py::test_residency_router_refuses_disallowed_external_calls PASSED [ 92%]
tests/unit/test_residency_router.py::test_zero_provider_calls_in_tests PASSED [ 93%]
tests/unit/test_residency_router.py::test_pii_sanitization_for_external_calls PASSED [ 93%]
tests/unit/test_s3_storage.py::test_s3_storage_initialization_defaults PASSED [ 94%]
tests/unit/test_s3_storage.py::test_s3_put_object_with_sse PASSED        [ 94%]
tests/unit/test_s3_storage.py::test_s3_put_original_with_object_lock_compliance PASSED [ 94%]
tests/unit/test_s3_storage.py::test_s3_put_object_graceful_fallback_when_object_lock_unsupported PASSED [ 95%]
tests/unit/test_s3_storage.py::test_s3_get_object_success_and_not_found PASSED [ 95%]
tests/unit/test_s3_storage.py::test_s3_presigned_urls PASSED             [ 96%]
tests/unit/test_s3_storage.py::test_s3_object_exists PASSED              [ 96%]
tests/unit/test_s3_storage.py::test_storage_factory_selection PASSED     [ 96%]
tests/unit/test_scanner.py::test_clean_document_scan_in_fixture_mode PASSED [ 97%]
tests/unit/test_scanner.py::test_eicar_signature_detection PASSED        [ 97%]
tests/unit/test_scanner.py::test_scanner_unavailable_fail_safe_quarantine PASSED [ 98%]
tests/unit/test_scanner.py::test_clamav_signature_status_fresh_and_stale PASSED [ 98%]
tests/unit/test_scanner.py::test_check_intake_health_paused_when_stale PASSED [ 98%]
tests/unit/test_scanner.py::test_check_intake_health_paused_when_scanner_down PASSED [ 99%]
tests/unit/test_scanner.py::test_check_intake_health_active_when_fresh PASSED [ 99%]
tests/unit/test_scanner.py::test_clamd_reply_nul_terminator_is_stripped PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\21263\Downloads\avenel-split\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\fitz\__init__.py:17
  C:\Users\21263\Downloads\avenel-split\.venv\Lib\site-packages\fitz\__init__.py:17: FutureWarning: The `fitz` API is deprecated and will be removed in future. Use `import pymupdf` instead.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================= 251 passed, 2 warnings in 175.27s (0:02:55) =================
npx openapi-typescript contracts/openapi.yaml -o src/api/schema.d.ts
✨ openapi-typescript 7.13.0
🚀 contracts/openapi.yaml → src/api/schema.d.ts [201ms]
git diff --exit-code -- src/api/schema.d.ts
npx tsc -b --noEmit
npm run build

> avenel-web@1.0.0 build
> tsc -b && vite build

vite v5.4.21 building for production...
transforming...
✓ 1620 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.47 kB │ gzip:  0.29 kB
dist/assets/index-CoF9zEnA.css   22.63 kB │ gzip:  5.00 kB
dist/assets/index-awwGe-FA.js   157.10 kB │ gzip: 42.00 kB
dist/assets/vendor-BWYUuZrD.js  163.87 kB │ gzip: 53.45 kB
✓ built in 5.17s
npx vitest run --reporter=default --reporter=json --outputFile=.vitest-results.json

 RUN  v2.1.9 C:/Users/21263/Downloads/avenel-split

 ✓ src/test/contrast-pairs.test.ts (1 test) 6ms
 ✓ src/auth/oidc.test.ts (7 tests) 19ms
 ✓ scripts/guards/guards.test.mjs (9 tests) 25ms
stderr | src/screens/QueueScreen.test.tsx > QueueScreen states (stubbed fetch) > shows the error state when the API is unreachable
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.

stderr | src/screens/QueueScreen.test.tsx > QueueScreen states (stubbed fetch) > shows the loading state first
Warning: An update to AuthProvider inside a test was not wrapped in act(...).

When testing, code that causes React state updates should be wrapped into act(...):

act(() => {
  /* fire events that update state */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser. Learn more at https://reactjs.org/link/wrap-tests-with-act
    at AuthProvider (C:\Users\21263\Downloads\avenel-split\src\auth\AuthProvider.tsx:10:25)
    at Router (C:\Users\21263\Downloads\avenel-split\node_modules\react-router\dist\umd\react-router.development.js:1203:17)
    at MemoryRouter (C:\Users\21263\Downloads\avenel-split\node_modules\react-router\dist\umd\react-router.development.js:1097:7)

 ✓ src/screens/QueueScreen.test.tsx (4 tests) 281ms
stderr | src/components/domain/ReconciliationScreen.test.tsx > ReconciliationScreen component > triggers onAcceptMatch when clicking Rapprocher button
Warning: An update to ReconciliationScreen inside a test was not wrapped in act(...).

When testing, code that causes React state updates should be wrapped into act(...):

act(() => {
  /* fire events that update state */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser. Learn more at https://reactjs.org/link/wrap-tests-with-act
    at ReconciliationScreen (C:\Users\21263\Downloads\avenel-split\src\components\domain\ReconciliationScreen.tsx:15:3)

stderr | src/components/domain/ReconciliationScreen.test.tsx > ReconciliationScreen component > triggers onRejectMatch when clicking Rejeter button
Warning: An update to ReconciliationScreen inside a test was not wrapped in act(...).

When testing, code that causes React state updates should be wrapped into act(...):

act(() => {
  /* fire events that update state */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser. Learn more at https://reactjs.org/link/wrap-tests-with-act
    at ReconciliationScreen (C:\Users\21263\Downloads\avenel-split\src\components\domain\ReconciliationScreen.tsx:15:3)

stderr | src/components/domain/ReconciliationScreen.test.tsx > ReconciliationScreen component > accepts match on Enter keypress
Warning: An update to ReconciliationScreen inside a test was not wrapped in act(...).

When testing, code that causes React state updates should be wrapped into act(...):

act(() => {
  /* fire events that update state */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser. Learn more at https://reactjs.org/link/wrap-tests-with-act
    at ReconciliationScreen (C:\Users\21263\Downloads\avenel-split\src\components\domain\ReconciliationScreen.tsx:15:3)

stderr | src/components/domain/ReconciliationScreen.test.tsx > ReconciliationScreen component > rejects match on Escape keypress
Warning: An update to ReconciliationScreen inside a test was not wrapped in act(...).

When testing, code that causes React state updates should be wrapped into act(...):

act(() => {
  /* fire events that update state */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser. Learn more at https://reactjs.org/link/wrap-tests-with-act
    at ReconciliationScreen (C:\Users\21263\Downloads\avenel-split\src\components\domain\ReconciliationScreen.tsx:15:3)

 ✓ src/components/domain/ReconciliationScreen.test.tsx (5 tests) 688ms
 ✓ src/components/domain/ProposalReview.test.tsx (6 tests) 984ms
   ✓ ProposalReview Component > renders balanced entry with accounts, totals and balance badge 349ms
 ✓ src/components/domain/Phase5Screens.test.tsx (11 tests) 1226ms
   ✓ Phase 5 UI Components > ApprovalScreen > renders dossier metadata, balanced totals, and allows approval when eligible 489ms
 ✓ scripts/guards/check_css_palette.test.mjs (4 tests) 7ms

 Test Files  8 passed (8)
      Tests  47 passed (47)
   Start at  15:40:26
   Duration  10.12s (transform 1.28s, setup 9.93s, collect 3.20s, tests 3.24s, environment 26.20s, prepare 4.99s)

JSON report written to C:/Users/21263/Downloads/avenel-split/.vitest-results.json
node scripts/guards/check_web_test_count.mjs
check_web_test_count: 47/47 passed, baseline 46
node scripts/guards/check_css_palette.mjs
check_css_palette: 1 file(s), 0 violation(s)
node scripts/guards/no_test_code_in_prod.mjs
no_test_code_in_prod: 0 violation(s)
node scripts/guards/no_e2e_interception.mjs
no_e2e_interception: 0 violation(s)
node scripts/guards/no_legacy_terms.mjs
no_legacy_terms: 0 violation(s)
docker compose up -d --build postgres keycloak clamav freshclam ocr migrate seed api worker web
Compose can now delegate builds to bake for better performance.
 To do so, set COMPOSE_BAKE=true.
#0 building with "desktop-linux" instance using docker driver

#1 [migrate internal] load build definition from Dockerfile.api
#1 transferring dockerfile: 2.14kB 0.0s done
#1 DONE 0.0s

#2 [migrate] resolve image config for docker-image://docker.io/docker/dockerfile:1
#2 DONE 1.0s

#3 [migrate] docker-image://docker.io/docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#3 CACHED

#4 [migrate internal] load metadata for docker.io/library/python:3.12-slim
#4 DONE 0.0s

#5 [migrate internal] load .dockerignore
#5 transferring context: 2B done
#5 DONE 0.0s

#6 [migrate builder 1/5] FROM docker.io/library/python:3.12-slim
#6 DONE 0.0s

#7 [migrate internal] load build context
#7 transferring context: 40.24kB 1.9s done
#7 DONE 1.9s

#8 [migrate runner  4/11] RUN groupadd -g 10001 appgroup &&     useradd -u 10001 -g appgroup -s /bin/false -m appuser
#8 CACHED

#9 [migrate runner  8/11] COPY --chown=appuser:appgroup jurisdiction /app/jurisdiction
#9 CACHED

#10 [migrate runner  5/11] COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
#10 CACHED

#11 [migrate runner  6/11] COPY --chown=appuser:appgroup avenel /app/avenel
#11 CACHED

#12 [migrate builder 4/5] COPY requirements.txt .
#12 CACHED

#13 [migrate runner  2/11] WORKDIR /app
#13 CACHED

#14 [migrate builder 3/5] RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     && rm -rf /var/lib/apt/lists/*
#14 CACHED

#15 [migrate builder 2/5] WORKDIR /build
#15 CACHED

#16 [migrate runner 10/11] COPY --chown=appuser:appgroup contracts /app/contracts
#16 CACHED

#17 [migrate runner  3/11] RUN apt-get update && apt-get install -y --no-install-recommends     libpq5     ca-certificates     libxcb1     libgl1     libglib2.0-0     && rm -rf /var/lib/apt/lists/*
#17 CACHED

#18 [migrate builder 5/5] RUN pip install --no-cache-dir --user -r requirements.txt
#18 CACHED

#19 [migrate runner  7/11] COPY --chown=appuser:appgroup apps /app/apps
#19 CACHED

#20 [migrate runner  9/11] COPY --chown=appuser:appgroup db /app/db
#20 CACHED

#21 [migrate runner 11/11] RUN mkdir -p /var/lib/avenel/storage && chown appuser:appgroup /var/lib/avenel/storage
#21 CACHED

#22 [migrate] exporting to image
#22 exporting layers done
#22 writing image sha256:f2376f5c4dab298756324408312a4b15858b1b3fb84360a792c5a259cf8ffc22 0.1s done
#22 naming to docker.io/library/avenel-split-migrate done
#22 DONE 0.1s

#23 [migrate] resolving provenance for metadata file
#23 DONE 0.0s

#24 [seed internal] load build definition from Dockerfile.api
#24 transferring dockerfile: 2.14kB done
#24 DONE 0.0s

#2 [seed] resolve image config for docker-image://docker.io/docker/dockerfile:1
#2 DONE 1.3s

#3 [seed] docker-image://docker.io/docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#3 CACHED

#4 [seed internal] load metadata for docker.io/library/python:3.12-slim
#4 DONE 0.0s

#25 [seed internal] load .dockerignore
#25 transferring context: 2B done
#25 DONE 0.0s

#6 [seed builder 1/5] FROM docker.io/library/python:3.12-slim
#6 DONE 0.0s

#26 [seed internal] load build context
#26 transferring context: 7.38kB 0.0s done
#26 DONE 0.0s

#14 [seed builder 3/5] RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     && rm -rf /var/lib/apt/lists/*
#14 CACHED

#27 [seed runner 10/11] COPY --chown=appuser:appgroup contracts /app/contracts
#27 CACHED

#28 [seed runner  9/11] COPY --chown=appuser:appgroup db /app/db
#28 CACHED

#8 [seed runner  4/11] RUN groupadd -g 10001 appgroup &&     useradd -u 10001 -g appgroup -s /bin/false -m appuser
#8 CACHED

#15 [seed builder 2/5] WORKDIR /build
#15 CACHED

#29 [seed runner  6/11] COPY --chown=appuser:appgroup avenel /app/avenel
#29 CACHED

#30 [seed builder 5/5] RUN pip install --no-cache-dir --user -r requirements.txt
#30 CACHED

#31 [seed builder 4/5] COPY requirements.txt .
#31 CACHED

#17 [seed runner  3/11] RUN apt-get update && apt-get install -y --no-install-recommends     libpq5     ca-certificates     libxcb1     libgl1     libglib2.0-0     && rm -rf /var/lib/apt/lists/*
#17 CACHED

#32 [seed runner  5/11] COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
#32 CACHED

#33 [seed runner  7/11] COPY --chown=appuser:appgroup apps /app/apps
#33 CACHED

#13 [seed runner  2/11] WORKDIR /app
#13 CACHED

#34 [seed runner  8/11] COPY --chown=appuser:appgroup jurisdiction /app/jurisdiction
#34 CACHED

#35 [seed runner 11/11] RUN mkdir -p /var/lib/avenel/storage && chown appuser:appgroup /var/lib/avenel/storage
#35 CACHED

#36 [seed] exporting to image
#36 exporting layers done
#36 writing image sha256:1a277275ffe09675d5639f8fc7d6929df59894e5566ab3eae6493d76aff8c290 done
#36 naming to docker.io/library/avenel-split-seed done
#36 DONE 0.0s

#37 [seed] resolving provenance for metadata file
#37 DONE 0.0s

#38 [api internal] load build definition from Dockerfile.api
#38 transferring dockerfile: 2.14kB done
#38 DONE 0.0s

#2 [api] resolve image config for docker-image://docker.io/docker/dockerfile:1
#2 DONE 1.6s

#3 [api] docker-image://docker.io/docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#3 CACHED

#4 [api internal] load metadata for docker.io/library/python:3.12-slim
#4 DONE 0.0s

#39 [api internal] load .dockerignore
#39 transferring context: 2B done
#39 DONE 0.0s

#6 [api builder 1/5] FROM docker.io/library/python:3.12-slim
#6 DONE 0.0s

#40 [api internal] load build context
#40 transferring context: 7.38kB 0.0s done
#40 DONE 0.0s

#8 [api runner  4/11] RUN groupadd -g 10001 appgroup &&     useradd -u 10001 -g appgroup -s /bin/false -m appuser
#8 CACHED

#17 [api runner  3/11] RUN apt-get update && apt-get install -y --no-install-recommends     libpq5     ca-certificates     libxcb1     libgl1     libglib2.0-0     && rm -rf /var/lib/apt/lists/*
#17 CACHED

#41 [api builder 4/5] COPY requirements.txt .
#41 CACHED

#42 [api builder 5/5] RUN pip install --no-cache-dir --user -r requirements.txt
#42 CACHED

#43 [api runner 10/11] COPY --chown=appuser:appgroup contracts /app/contracts
#43 CACHED

#13 [api runner  2/11] WORKDIR /app
#13 CACHED

#44 [api runner  8/11] COPY --chown=appuser:appgroup jurisdiction /app/jurisdiction
#44 CACHED

#14 [api builder 3/5] RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     && rm -rf /var/lib/apt/lists/*
#14 CACHED

#45 [api runner  7/11] COPY --chown=appuser:appgroup apps /app/apps
#45 CACHED

#46 [api runner  9/11] COPY --chown=appuser:appgroup db /app/db
#46 CACHED

#47 [api runner  5/11] COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
#47 CACHED

#48 [api runner  6/11] COPY --chown=appuser:appgroup avenel /app/avenel
#48 CACHED

#15 [api builder 2/5] WORKDIR /build
#15 CACHED

#49 [api runner 11/11] RUN mkdir -p /var/lib/avenel/storage && chown appuser:appgroup /var/lib/avenel/storage
#49 CACHED

#50 [api] exporting to image
#50 exporting layers done
#50 writing image sha256:4ed076108dc5ab7fe31eb73ee30078ab7f4a4205c5f7e90823e746896cc535b7 done
#50 naming to docker.io/library/avenel-split-api done
#50 DONE 0.0s

#51 [api] resolving provenance for metadata file
#51 DONE 0.0s

#52 [worker internal] load build definition from Dockerfile.api
#52 transferring dockerfile: 2.14kB 0.0s done
#52 DONE 0.0s

#53 [web internal] load build definition from Dockerfile.web
#53 transferring dockerfile: 690B done
#53 DONE 0.0s

#2 [web] resolve image config for docker-image://docker.io/docker/dockerfile:1
#2 DONE 1.9s

#3 [web] docker-image://docker.io/docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#3 CACHED

#4 [worker internal] load metadata for docker.io/library/python:3.12-slim
#4 DONE 0.0s

#54 [worker internal] load .dockerignore
#54 transferring context: 2B done
#54 DONE 0.0s

#6 [worker builder 1/5] FROM docker.io/library/python:3.12-slim
#6 DONE 0.0s

#55 [worker internal] load build context
#55 transferring context: 7.38kB 0.0s done
#55 DONE 0.0s

#56 [worker runner 10/11] COPY --chown=appuser:appgroup contracts /app/contracts
#56 CACHED

#13 [worker runner  2/11] WORKDIR /app
#13 CACHED

#57 [worker runner  9/11] COPY --chown=appuser:appgroup db /app/db
#57 CACHED

#58 [worker runner  5/11] COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
#58 CACHED

#8 [worker runner  4/11] RUN groupadd -g 10001 appgroup &&     useradd -u 10001 -g appgroup -s /bin/false -m appuser
#8 CACHED

#59 [worker runner  6/11] COPY --chown=appuser:appgroup avenel /app/avenel
#59 CACHED

#15 [worker builder 2/5] WORKDIR /build
#15 CACHED

#14 [worker builder 3/5] RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     && rm -rf /var/lib/apt/lists/*
#14 CACHED

#60 [worker builder 5/5] RUN pip install --no-cache-dir --user -r requirements.txt
#60 CACHED

#61 [worker builder 4/5] COPY requirements.txt .
#61 CACHED

#62 [worker runner  7/11] COPY --chown=appuser:appgroup apps /app/apps
#62 CACHED

#17 [worker runner  3/11] RUN apt-get update && apt-get install -y --no-install-recommends     libpq5     ca-certificates     libxcb1     libgl1     libglib2.0-0     && rm -rf /var/lib/apt/lists/*
#17 CACHED

#63 [worker runner  8/11] COPY --chown=appuser:appgroup jurisdiction /app/jurisdiction
#63 CACHED

#64 [worker runner 11/11] RUN mkdir -p /var/lib/avenel/storage && chown appuser:appgroup /var/lib/avenel/storage
#64 CACHED

#65 [worker] exporting to image
#65 exporting layers done
#65 writing image sha256:33c85e545ede04ba01f3a2d455e693f5ac591cc421a1ac8eb5007e59bf301da5 done
#65 naming to docker.io/library/avenel-split-worker
#65 naming to docker.io/library/avenel-split-worker done
#65 DONE 0.0s

#66 [worker] resolving provenance for metadata file
#66 DONE 0.0s

#67 [web internal] load metadata for docker.io/nginxinc/nginx-unprivileged:alpine
#67 DONE 0.8s

#68 [web internal] load metadata for docker.io/library/node:20-alpine
#68 DONE 0.8s

#69 [web internal] load .dockerignore
#69 transferring context: 2B done
#69 DONE 0.0s

#70 [web builder 1/6] FROM docker.io/library/node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293
#70 DONE 0.0s

#71 [web runner 1/3] FROM docker.io/nginxinc/nginx-unprivileged:alpine@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e
#71 DONE 0.0s

#72 [web internal] load build context
#72 transferring context: 66.71MB 5.0s
#72 transferring context: 121.24MB 10.1s
#72 transferring context: 188.81MB 15.2s
#72 transferring context: 257.02MB 20.3s
#72 transferring context: 323.70MB 25.4s
#72 transferring context: 389.45MB 30.5s
#72 transferring context: 453.31MB 35.5s
#72 transferring context: 523.11MB 40.7s
#72 transferring context: 589.04MB 45.7s
#72 transferring context: 652.46MB 50.7s
#72 transferring context: 698.93MB 55.8s
#72 transferring context: 750.06MB 60.9s
#72 transferring context: 780.24MB 65.9s
#72 transferring context: 816.10MB 71.0s
#72 transferring context: 860.83MB 76.0s
#72 transferring context: 925.18MB 81.1s
#72 transferring context: 990.06MB 86.2s
#72 transferring context: 1.06GB 91.2s
#72 transferring context: 1.11GB 96.2s
#72 transferring context: 1.16GB 99.6s done
#72 DONE 100.0s

#73 [web builder 2/6] WORKDIR /build
#73 CACHED

#74 [web builder 3/6] COPY package*.json ./
#74 CACHED

#75 [web builder 4/6] RUN npm ci --no-audit
#75 CACHED

#76 [web builder 5/6] COPY . .
#76 DONE 17.3s

#77 [web builder 6/6] RUN npm run build
#77 0.907 
#77 0.907 > avenel-web@1.0.0 build
#77 0.907 > tsc -b && vite build
#77 0.907 
#77 13.15 vite v5.4.21 building for production...
#77 13.25 transforming...
#77 17.85 ✓ 1620 modules transformed.
#77 18.12 rendering chunks...
#77 18.15 computing gzip size...
#77 18.17 dist/index.html                   0.47 kB │ gzip:  0.29 kB
#77 18.17 dist/assets/index-CoF9zEnA.css   22.63 kB │ gzip:  5.00 kB
#77 18.17 dist/assets/index-awwGe-FA.js   157.10 kB │ gzip: 42.00 kB
#77 18.17 dist/assets/vendor-BWYUuZrD.js  163.87 kB │ gzip: 53.45 kB
#77 18.17 ✓ built in 4.97s
#77 DONE 18.3s

#78 [web runner 2/3] COPY --from=builder /build/dist /usr/share/nginx/html
#78 CACHED

#79 [web runner 3/3] COPY docker/nginx.conf /etc/nginx/nginx.conf
#79 CACHED

#80 [web] exporting to image
#80 exporting layers done
#80 writing image sha256:a25c7a55cd120d03a14583930fa1cfc424467ee90162d1a63cbd78a6b3dfbb6c done
#80 naming to docker.io/library/avenel-split-web done
#80 DONE 0.0s

#81 [web] resolving provenance for metadata file
#81 DONE 0.0s
 api  Built
 migrate  Built
 seed  Built
 web  Built
 worker  Built
 Network avenel-split_default  Creating
 Network avenel-split_default  Created
 Volume "avenel-split_pgdata"  Creating
 Volume "avenel-split_pgdata"  Created
 Volume "avenel-split_docstore"  Creating
 Volume "avenel-split_docstore"  Created
 Volume "avenel-split_clamav_db"  Creating
 Volume "avenel-split_clamav_db"  Created
 Container avenel-freshclam  Creating
 Container avenel-keycloak  Creating
 Container avenel-ocr-stub  Creating
 Container avenel-clamav  Creating
 Container avenel-postgres  Creating
 Container avenel-ocr-stub  Created
 Container avenel-postgres  Created
 Container avenel-migrate  Creating
 Container avenel-freshclam  Created
 Container avenel-keycloak  Created
 Container avenel-migrate  Created
 Container avenel-seed  Creating
 Container avenel-seed  Created
 Container avenel-clamav  Created
 Container avenel-api  Creating
 Container avenel-api  Created
 Container avenel-worker  Creating
 Container avenel-web  Creating
 Container avenel-worker  Created
 Container avenel-web  Created
 Container avenel-freshclam  Starting
 Container avenel-keycloak  Starting
 Container avenel-clamav  Starting
 Container avenel-postgres  Starting
 Container avenel-ocr-stub  Starting
 Container avenel-ocr-stub  Started
 Container avenel-clamav  Started
 Container avenel-freshclam  Started
 Container avenel-postgres  Started
 Container avenel-postgres  Waiting
 Container avenel-keycloak  Started
 Container avenel-postgres  Healthy
 Container avenel-migrate  Starting
 Container avenel-migrate  Started
 Container avenel-migrate  Waiting
 Container avenel-migrate  Exited
 Container avenel-seed  Starting
 Container avenel-seed  Started
 Container avenel-clamav  Waiting
 Container avenel-seed  Waiting
 Container avenel-keycloak  Waiting
 Container avenel-seed  Exited
 Container avenel-clamav  Healthy
 Container avenel-keycloak  Healthy
 Container avenel-api  Starting
 Container avenel-api  Started
 Container avenel-api  Waiting
 Container avenel-api  Waiting
 Container avenel-api  Healthy
 Container avenel-api  Healthy
 Container avenel-web  Starting
 Container avenel-worker  Starting
 Container avenel-worker  Started
 Container avenel-web  Started
node scripts/guards/wait_for_stack.mjs
wait_for_stack: intake paused (ClamAV signatures not fresh yet), asking clamd to reload
wait_for_stack: api /health/ready green: http://localhost:8000/health/ready {"status":"ready","service":"avenel-api","database":"ok","kms":"ok","clamav":"ok","intake_paused":false}
wait_for_stack: keycloak realm green: http://localhost:8080/realms/avenel/.well-known/openid-configuration {"issuer":"http://localhost:8080/realms/avenel","authorization_endpoint":"http://localhost:8080/realms/avenel/protocol/openid-connect/auth","token_endpoint":"ht
wait_for_stack: web /healthz (nginx) green: http://localhost:5173/healthz healthy 
npx playwright install chromium
rm -rf docs/reports/phase-5c-1/e2e-browser-api-requests.log .e2e-state
npx playwright test --grep-invert @api-down

Running 6 tests using 1 worker

2026-11-06T14:45:16.387Z [login-queue] GET http://localhost:8000/v1/me -> 200 bearer_jwt=true
2026-11-06T14:45:16.397Z [login-queue] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:45:16.398Z [login-queue] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
[login-queue] direct GET http://localhost:8000/v1/me -> 200 tenant_id=5c1e2e00-0000-4000-8000-0000000000a1 role=accountant
  ok 1 [chromium] › e2e\login-queue.spec.ts:6:1 › accountant logs in with TOTP, sees seeded queue from the API, logs out (8.2s)
2026-11-06T14:45:30.404Z [phase1-accountant] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:45:30.440Z [phase1-accountant] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:45:30.441Z [phase1-accountant] GET http://localhost:8000/v1/me -> 200 bearer_jwt=true
2026-11-06T14:45:30.461Z [phase1-accountant] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:45:30.988Z [phase1-accountant] POST http://localhost:8000/v1/client-entities -> 201 bearer_jwt=true
2026-11-06T14:45:31.019Z [phase1-accountant] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:45:31.524Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc -> 200 bearer_jwt=true
2026-11-06T14:45:31.585Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:45:31.606Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:45:31.608Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/periods -> 200 bearer_jwt=true
2026-11-06T14:45:31.636Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:45:31.704Z [phase1-accountant] POST http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/periods -> 201 bearer_jwt=true
2026-11-06T14:45:31.782Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/periods -> 200 bearer_jwt=true
2026-11-06T14:45:31.951Z [phase1-accountant] POST http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/periods -> 409 bearer_jwt=true body={"type":"about:blank","title":"Conflit d'état","status":409,"detail":"La période 2026-10 existe déjà pour cette entreprise.","instance":"/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/periods"}
2026-11-06T14:45:32.103Z [phase1-accountant] POST http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts/seed-cgnc -> 200 bearer_jwt=true
2026-11-06T14:45:32.136Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:45:32.560Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:45:32.562Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:45:32.680Z [phase1-accountant] POST http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts/import-file -> 200 bearer_jwt=true
2026-11-06T14:45:32.719Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:45:32.721Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:45:32.755Z [phase1-accountant] GET http://localhost:8000/v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:45:33.178Z [phase1-accountant] GET http://localhost:8000/v1/compliance/dpa -> 200 bearer_jwt=true
2026-11-06T14:45:33.424Z [phase1-accountant] GET http://localhost:8000/v1/compliance/cndp-dossier -> 200 bearer_jwt=true
  ok 2 [chromium] › e2e\phase1-clients.spec.ts:21:1 › accountant: create company, open period, overlap refused, CGNC + file import, DPA/CNDP (16.4s)
2026-11-06T14:45:35.312Z [phase1-client-user] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:45:35.314Z [phase1-client-user] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:45:35.317Z [phase1-client-user] GET http://localhost:8000/v1/me -> 200 bearer_jwt=true
2026-11-06T14:45:35.562Z [phase1-client-user] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
[phase1-client-user] direct GET http://localhost:8000/v1/client-entities/6be99dfa-9baa-4e3e-8868-d0b1c83ddf9b -> 404
2026-11-06T14:45:35.895Z [phase1-client-user] GET http://localhost:8000/v1/client-entities/6be99dfa-9baa-4e3e-8868-d0b1c83ddf9b -> 404 bearer_jwt=true body={"type":"about:blank","title":"Ressource introuvable","status":404,"detail":"Entreprise cliente introuvable.","instance":"/v1/client-entities/6be99dfa-9baa-4e3e-8868-d0b1c83ddf9b"}
  ok 3 [chromium] › e2e\phase1-clients.spec.ts:101:1 › client user sees only the company in scope (browser and API) (2.3s)
2026-11-06T14:46:00.540Z [phase2-accountant] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:46:00.549Z [phase2-accountant] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:00.563Z [phase2-accountant] GET http://localhost:8000/v1/me -> 200 bearer_jwt=true
2026-11-06T14:46:00.723Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e -> 200 bearer_jwt=true
2026-11-06T14:46:00.788Z [phase2-accountant] GET http://localhost:8000/v1/client-entities/6be99dfa-9baa-4e3e-8868-d0b1c83ddf9b -> 200 bearer_jwt=true
2026-11-06T14:46:00.864Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/issues -> 200 bearer_jwt=true
2026-11-06T14:46:00.883Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/documents -> 200 bearer_jwt=true
2026-11-06T14:46:03.488Z [phase2-accountant] POST http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/uploads -> 201 bearer_jwt=true
2026-11-06T14:46:06.282Z [phase2-accountant] PUT http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/content -> 200 bearer_jwt=true
2026-11-06T14:46:12.268Z [phase2-accountant] POST http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce:complete-upload -> 200 bearer_jwt=true
2026-11-06T14:46:12.322Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e -> 200 bearer_jwt=true
2026-11-06T14:46:12.410Z [phase2-accountant] GET http://localhost:8000/v1/client-entities/6be99dfa-9baa-4e3e-8868-d0b1c83ddf9b -> 200 bearer_jwt=true
2026-11-06T14:46:12.500Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/issues -> 200 bearer_jwt=true
2026-11-06T14:46:12.514Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/documents -> 200 bearer_jwt=true
2026-11-06T14:46:12.811Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce -> 200 bearer_jwt=true
2026-11-06T14:46:12.859Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/extraction -> 200 bearer_jwt=true
2026-11-06T14:46:12.921Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/pages/1/image -> 200 bearer_jwt=true
2026-11-06T14:46:13.040Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/pages/2/image -> 404 bearer_jwt=true body={"type":"about:blank","title":"Ressource introuvable","status":404,"detail":"Page introuvable.","instance":"/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/pages/2/image"}
[phase2-accountant] total_ttc bbox api=[0.0992,0.359,0.3226,0.3738] drawn=[0.099,0.359,0.323,0.374]
2026-11-06T14:46:13.956Z [phase2-accountant] PATCH http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/extraction -> 200 bearer_jwt=true
2026-11-06T14:46:14.000Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce -> 200 bearer_jwt=true
2026-11-06T14:46:14.094Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/extraction -> 200 bearer_jwt=true
2026-11-06T14:46:14.138Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/pages/1/image -> 200 bearer_jwt=true
2026-11-06T14:46:14.245Z [phase2-accountant] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/pages/2/image -> 404 bearer_jwt=true body={"type":"about:blank","title":"Ressource introuvable","status":404,"detail":"Page introuvable.","instance":"/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/pages/2/image"}
2026-11-06T14:46:14.339Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e -> 200 bearer_jwt=true
2026-11-06T14:46:14.369Z [phase2-accountant] GET http://localhost:8000/v1/client-entities/6be99dfa-9baa-4e3e-8868-d0b1c83ddf9b -> 200 bearer_jwt=true
2026-11-06T14:46:14.481Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/issues -> 200 bearer_jwt=true
2026-11-06T14:46:14.482Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/documents -> 200 bearer_jwt=true
2026-11-06T14:46:14.571Z [phase2-accountant] POST http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/uploads -> 201 bearer_jwt=true
2026-11-06T14:46:14.670Z [phase2-accountant] PUT http://localhost:8000/v1/documents/1605e861-b8b9-4737-a59c-282782c18168/content -> 200 bearer_jwt=true
2026-11-06T14:46:14.778Z [phase2-accountant] POST http://localhost:8000/v1/documents/1605e861-b8b9-4737-a59c-282782c18168:complete-upload -> 422 bearer_jwt=true body={"type":"about:blank","title":"Entité non traitable","status":422,"detail":"Pièce mise en quarantaine : logiciel malveillant détecté (Eicar-Test-Signature). Elle ne sera pas lue. Demandez une copie saine au client.","instance":"/v1/documents/1605e861-b8b9-4737-a59c-282782c18168:complete-upload"}
2026-11-06T14:46:14.805Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e -> 200 bearer_jwt=true
2026-11-06T14:46:14.874Z [phase2-accountant] GET http://localhost:8000/v1/client-entities/6be99dfa-9baa-4e3e-8868-d0b1c83ddf9b -> 200 bearer_jwt=true
2026-11-06T14:46:14.957Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/issues -> 200 bearer_jwt=true
2026-11-06T14:46:14.971Z [phase2-accountant] GET http://localhost:8000/v1/work-requests/dbec3a38-37e8-4aca-884f-0bb9c1f1841e/documents -> 200 bearer_jwt=true
  ok 4 [chromium] › e2e\phase2-intake.spec.ts:26:1 › accountant uploads a scanned invoice, it is read, reviewed and corrected (39.2s)
2026-11-06T14:46:16.511Z [phase2-client-user] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:46:16.820Z [phase2-client-user] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:17.366Z [phase2-client-user] GET http://localhost:8000/v1/me -> 200 bearer_jwt=true
[phase2-client-user] direct GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce -> 404
[phase2-client-user] direct GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/extraction -> 404
[phase2-client-user] direct GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce/pages/1/image -> 404
2026-11-06T14:46:17.753Z [phase2-client-user] GET http://localhost:8000/v1/documents/e4b794d9-83f0-459a-9a0c-0967be1f53ce -> 404 bearer_jwt=true body=
  ok 5 [chromium] › e2e\phase2-intake.spec.ts:105:1 › client user cannot open a document of another company (2.5s)
2026-11-06T14:46:19.422Z [phase3-expert] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
[phase3-expert] token amr=["pwd","otp"]
2026-11-06T14:46:19.456Z [phase3-expert] GET http://localhost:8000/v1/me -> 200 bearer_jwt=true
2026-11-06T14:46:19.495Z [phase3-expert] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:19.607Z [phase3-expert] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:19.713Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:19.839Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:19.851Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:19.852Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/periods -> 200 bearer_jwt=true
2026-11-06T14:46:19.919Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:19.990Z [phase3-expert] POST http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts/seed-cgnc -> 200 bearer_jwt=true
2026-11-06T14:46:20.069Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:20.092Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:20.164Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:20.513Z [phase3-expert] PUT http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:20.614Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:20.616Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:21.071Z [phase3-expert] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:46:21.073Z [phase3-expert] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:21.161Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039 -> 200 bearer_jwt=true
2026-11-06T14:46:21.199Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:21.334Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/issues -> 200 bearer_jwt=true
2026-11-06T14:46:21.336Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/documents -> 200 bearer_jwt=true
2026-11-06T14:46:24.072Z [phase3-expert] POST http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/uploads -> 201 bearer_jwt=true
2026-11-06T14:46:26.625Z [phase3-expert] PUT http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd/content -> 200 bearer_jwt=true
2026-11-06T14:46:29.708Z [phase3-expert] POST http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd:complete-upload -> 200 bearer_jwt=true
2026-11-06T14:46:29.755Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039 -> 200 bearer_jwt=true
2026-11-06T14:46:29.839Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:29.987Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/issues -> 200 bearer_jwt=true
2026-11-06T14:46:29.990Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/documents -> 200 bearer_jwt=true
2026-11-06T14:46:30.219Z [phase3-expert] POST http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd:generate-proposal -> 200 bearer_jwt=true
2026-11-06T14:46:30.253Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039 -> 200 bearer_jwt=true
2026-11-06T14:46:30.326Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:30.441Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/proposals -> 200 bearer_jwt=true
2026-11-06T14:46:30.482Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/documents -> 200 bearer_jwt=true
2026-11-06T14:46:30.483Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/issues -> 200 bearer_jwt=true
2026-11-06T14:46:30.549Z [phase3-expert] GET http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd/pages/1/image -> 200 bearer_jwt=true
[phase3-expert] line 1 evidence api=[0.0992,0.3111,0.3121,0.3259] drawn=[0.099,0.311,0.312,0.326]
[phase3-expert] proposal lines=3 debit=12000 credit=12000
  ok 6 [chromium] › e2e\phase3-proposals.spec.ts:13:1 › expert approves VAT account, proposes an entry from a read invoice, reviews it (13.5s)

  6 passed (1.4m)
docker compose stop api
 Container avenel-api  Stopping
 Container avenel-api  Stopped
npx playwright test --grep @api-down

Running 1 test using 1 worker

2026-11-06T14:46:42.843Z [api-down] GET http://localhost:8000/v1/work-requests -> FAILED net::ERR_CONNECTION_REFUSED
2026-11-06T14:46:42.844Z [api-down] GET http://localhost:8000/v1/client-entities -> FAILED net::ERR_CONNECTION_REFUSED
2026-11-06T14:46:42.845Z [api-down] GET http://localhost:8000/v1/me -> FAILED net::ERR_CONNECTION_REFUSED
  ok 1 [chromium] › e2e\queue-api-down.spec.ts:6:1 › @api-down queue shows the error state when the API is down (4.2s)

  1 passed (5.9s)
docker compose start api
 Container avenel-postgres  Waiting
 Container avenel-postgres  Healthy
 Container avenel-migrate  Starting
 Container avenel-migrate  Started
 Container avenel-migrate  Waiting
 Container avenel-migrate  Exited
 Container avenel-seed  Starting
 Container avenel-seed  Started
 Container avenel-seed  Waiting
 Container avenel-keycloak  Waiting
 Container avenel-clamav  Waiting
 Container avenel-clamav  Healthy
 Container avenel-keycloak  Healthy
 Container avenel-seed  Exited
 Container avenel-api  Starting
 Container avenel-api  Started
C:/ProgramData/chocolatey/lib/make/tools/install/bin/make.exe e2e-down
make[1]: Entering directory 'C:/Users/21263/Downloads/avenel-split'
docker compose logs --no-color --timestamps api > docs/reports/phase-5c-1/e2e-api-container.log 2>&1 || true
docker compose down -v
 Container avenel-ocr-stub  Stopping
 Container avenel-worker  Stopping
 Container avenel-freshclam  Stopping
 Container avenel-web  Stopping
 Container avenel-freshclam  Stopped
 Container avenel-freshclam  Removing
 Container avenel-freshclam  Removed
 Container avenel-web  Stopped
 Container avenel-web  Removing
 Container avenel-web  Removed
 Container avenel-worker  Stopped
 Container avenel-worker  Removing
 Container avenel-worker  Removed
 Container avenel-api  Stopping
 Container avenel-ocr-stub  Stopped
 Container avenel-ocr-stub  Removing
 Container avenel-ocr-stub  Removed
 Container avenel-api  Stopped
 Container avenel-api  Removing
 Container avenel-api  Removed
 Container avenel-seed  Stopping
 Container avenel-keycloak  Stopping
 Container avenel-clamav  Stopping
 Container avenel-seed  Stopped
 Container avenel-seed  Removing
 Container avenel-seed  Removed
 Container avenel-migrate  Stopping
 Container avenel-migrate  Stopped
 Container avenel-migrate  Removing
 Container avenel-migrate  Removed
 Container avenel-postgres  Stopping
 Container avenel-clamav  Stopped
 Container avenel-clamav  Removing
 Container avenel-clamav  Removed
 Container avenel-postgres  Stopped
 Container avenel-postgres  Removing
 Container avenel-postgres  Removed
 Container avenel-keycloak  Stopped
 Container avenel-keycloak  Removing
 Container avenel-keycloak  Removed
 Volume avenel-split_pgdata  Removing
 Network avenel-split_default  Removing
 Volume avenel-split_docstore  Removing
 Volume avenel-split_pgdata  Removed
 Volume avenel-split_clamav_db  Removing
 Volume avenel-split_docstore  Removed
 Volume avenel-split_clamav_db  Removed
 Network avenel-split_default  Removed
make[1]: Leaving directory 'C:/Users/21263/Downloads/avenel-split'
MAKE_CI_EXIT=0
```

</details>

## E2E request log (Phase 3 test)

Browser side:

```
2026-11-06T14:46:19.422Z [phase3-expert] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:46:19.456Z [phase3-expert] GET http://localhost:8000/v1/me -> 200 bearer_jwt=true
2026-11-06T14:46:19.495Z [phase3-expert] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:19.607Z [phase3-expert] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:19.713Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:19.839Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:19.851Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:19.852Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/periods -> 200 bearer_jwt=true
2026-11-06T14:46:19.919Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:19.990Z [phase3-expert] POST http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts/seed-cgnc -> 200 bearer_jwt=true
2026-11-06T14:46:20.069Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:20.092Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:20.164Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:20.513Z [phase3-expert] PUT http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:20.614Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings -> 200 bearer_jwt=true
2026-11-06T14:46:20.616Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/chart-accounts -> 200 bearer_jwt=true
2026-11-06T14:46:21.071Z [phase3-expert] GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true
2026-11-06T14:46:21.073Z [phase3-expert] GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true
2026-11-06T14:46:21.161Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039 -> 200 bearer_jwt=true
2026-11-06T14:46:21.199Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:21.334Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/issues -> 200 bearer_jwt=true
2026-11-06T14:46:21.336Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/documents -> 200 bearer_jwt=true
2026-11-06T14:46:24.072Z [phase3-expert] POST http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/uploads -> 201 bearer_jwt=true
2026-11-06T14:46:26.625Z [phase3-expert] PUT http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd/content -> 200 bearer_jwt=true
2026-11-06T14:46:29.708Z [phase3-expert] POST http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd:complete-upload -> 200 bearer_jwt=true
2026-11-06T14:46:29.755Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039 -> 200 bearer_jwt=true
2026-11-06T14:46:29.839Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:29.987Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/issues -> 200 bearer_jwt=true
2026-11-06T14:46:29.990Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/documents -> 200 bearer_jwt=true
2026-11-06T14:46:30.219Z [phase3-expert] POST http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd:generate-proposal -> 200 bearer_jwt=true
2026-11-06T14:46:30.253Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039 -> 200 bearer_jwt=true
2026-11-06T14:46:30.326Z [phase3-expert] GET http://localhost:8000/v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af -> 200 bearer_jwt=true
2026-11-06T14:46:30.441Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/proposals -> 200 bearer_jwt=true
2026-11-06T14:46:30.482Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/documents -> 200 bearer_jwt=true
2026-11-06T14:46:30.483Z [phase3-expert] GET http://localhost:8000/v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/issues -> 200 bearer_jwt=true
2026-11-06T14:46:30.549Z [phase3-expert] GET http://localhost:8000/v1/documents/fa90e123-8ff7-46ba-82e0-789c2a156ddd/pages/1/image -> 200 bearer_jwt=true
```

API container side (tax mappings and proposals):

```
2026-11-06T14:45:31.576821611Z INFO:     192.168.32.1:46174 - "GET /v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/tax-mappings HTTP/1.1" 200 OK
2026-11-06T14:45:32.557672691Z INFO:     192.168.32.1:46208 - "GET /v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/tax-mappings HTTP/1.1" 200 OK
2026-11-06T14:45:32.717631361Z INFO:     192.168.32.1:46208 - "GET /v1/client-entities/acbefa25-4623-4493-ab19-fa09c59b7ecc/tax-mappings HTTP/1.1" 200 OK
2026-11-06T14:46:19.834498729Z INFO:     192.168.32.1:58394 - "GET /v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings HTTP/1.1" 200 OK
2026-11-06T14:46:20.065683686Z INFO:     192.168.32.1:58372 - "GET /v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings HTTP/1.1" 200 OK
2026-11-06T14:46:20.509032604Z INFO:     192.168.32.1:58382 - "PUT /v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings HTTP/1.1" 200 OK
2026-11-06T14:46:20.609308812Z INFO:     192.168.32.1:58382 - "GET /v1/client-entities/c9513328-8334-453d-8d5f-8ef1ff91b7af/tax-mappings HTTP/1.1" 200 OK
2026-11-06T14:46:30.436949049Z INFO:     192.168.32.1:58408 - "GET /v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/proposals HTTP/1.1" 200 OK
2026-11-06T14:46:31.108847939Z INFO:     192.168.32.1:47248 - "GET /v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/proposals HTTP/1.1" 200 OK
2026-11-06T14:46:31.323583483Z INFO:     192.168.32.1:47248 - "GET /v1/work-requests/fb91997f-1fa4-48fa-991f-35a5eaaae039/proposals HTTP/1.1" 200 OK
```

## Screenshots

| VAT account approved by the expert | Proposed entry with evidence box |
|---|---|
| ![](phase-3/01-tax-mapping-approved.png) | ![](phase-3/02-review-entry-evidence.png) |

## Unverified

- **GitHub CI** for these commits (not pushed).
- **Golden tests use hand-built inputs**; only one real-document path (standard 20 % purchase) is covered end to end. Sales, credit notes, fixed assets, multi-rate and FX from real scans are not.
- **Account suggester** proposes 6111 for the e2e invoice ("Fournitures de bureau"), which an accountant would likely book elsewhere; the suggestion is not reviewed against a professional.
- **Line editing in the browser** (revision 2) is covered by API tests, not by the e2e.
- **Production Keycloak**: the realm export changes are not applied to any real instance.
- **The 48 `source_cited` and 30 `needs_expert` rules** still need a professional's signature.
- **Supplier names without spaces** from OCR still flow into entry labels.

## Stubbed

- No LLM provider (router returns a placeholder success when allowed); the account suggester runs on counterparty history and rules.
- Worker still a sleep loop; seed data via `scripts/seed_e2e.py` (now with a registered professional test user).
