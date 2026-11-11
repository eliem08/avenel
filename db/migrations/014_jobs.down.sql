-- 014_jobs.down.sql
DROP FUNCTION IF EXISTS app.claim_next_job(integer);
DROP TABLE IF EXISTS jobs;
