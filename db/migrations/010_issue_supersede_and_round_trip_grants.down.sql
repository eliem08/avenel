-- 010_issue_supersede_and_round_trip_grants.down.sql
REVOKE SELECT, INSERT ON export_round_trips FROM avenel_app;
ALTER TABLE issues DROP CONSTRAINT issues_superseded_at_check;
ALTER TABLE issues DROP COLUMN superseded_at;
UPDATE issues SET status = 'resolved', resolution = 'fixed', resolved_at = now(),
  resolution_note = coalesce(resolution_note, 'superseded (rolled back from migration 010)')
  WHERE status = 'superseded';
ALTER TABLE issues DROP CONSTRAINT issues_status_check;
ALTER TABLE issues ADD CONSTRAINT issues_status_check
  CHECK (status IN ('open','assigned','waiting_client','resolved','waived'));
