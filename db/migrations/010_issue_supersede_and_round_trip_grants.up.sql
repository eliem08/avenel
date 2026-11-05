-- 010_issue_supersede_and_round_trip_grants.up.sql
-- Found when the API test suite first ran as avenel_app (Part C.5) instead of a superuser.
--
-- 1. Re-validating a document used DELETE FROM issues, which avenel_app may not do, so every
--    real intake failed. Issues are now superseded, never deleted: a new status 'superseded'
--    keeps the full history (human decision, Phase 1 completion, 5 Nov 2026).
-- 2. export_round_trips (migration 008) was created after the blanket grant in 002 and was
--    never granted to avenel_app, so recording a round trip failed. Round trips are an
--    append-only record: SELECT and INSERT only.

ALTER TABLE issues DROP CONSTRAINT issues_status_check;
ALTER TABLE issues ADD CONSTRAINT issues_status_check
  CHECK (status IN ('open','assigned','waiting_client','resolved','waived','superseded'));

ALTER TABLE issues ADD COLUMN superseded_at timestamptz;
ALTER TABLE issues ADD CONSTRAINT issues_superseded_at_check
  CHECK ((status = 'superseded') = (superseded_at IS NOT NULL));

GRANT SELECT, INSERT ON export_round_trips TO avenel_app;
