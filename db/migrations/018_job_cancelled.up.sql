-- 018_job_cancelled.up.sql
-- Phase 8d: a job of a cancelled monthly file ends as 'cancelled' (finished, its step never run).
-- Replaces the two status checks of 014; 014 itself is not edited.

ALTER TABLE jobs DROP CONSTRAINT jobs_status_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_status_check
  CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled'));

ALTER TABLE jobs DROP CONSTRAINT jobs_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_finished_check
  CHECK ((status IN ('succeeded', 'failed', 'cancelled')) = (finished_at IS NOT NULL));
