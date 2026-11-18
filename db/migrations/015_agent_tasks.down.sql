-- 015_agent_tasks.down.sql
DROP TABLE IF EXISTS agent_tasks;
DELETE FROM jobs WHERE step IN ('prepare_proposals', 'reconcile');
ALTER TABLE jobs DROP CONSTRAINT jobs_step_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_step_check CHECK (step IN ('read_document'));
