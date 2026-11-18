-- 017_claim_jobs_by_step.down.sql
DROP FUNCTION IF EXISTS app.claim_next_job_for_steps(integer, text[]);
