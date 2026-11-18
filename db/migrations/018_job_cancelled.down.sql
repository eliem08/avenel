-- 018_job_cancelled.down.sql
-- Cancelled jobs become 'failed' (with the reason kept in last_error) so the 014 checks hold again.

UPDATE jobs SET status = 'failed', last_error = COALESCE(last_error, 'cancelled with its monthly file')
WHERE status = 'cancelled';

ALTER TABLE jobs DROP CONSTRAINT jobs_finished_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_check
  CHECK ((status IN ('succeeded', 'failed')) = (finished_at IS NOT NULL));

ALTER TABLE jobs DROP CONSTRAINT jobs_status_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_status_check
  CHECK (status IN ('queued', 'running', 'succeeded', 'failed'));
