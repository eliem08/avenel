-- 017_claim_jobs_by_step.up.sql
-- A worker can be limited to some job steps, so a slow AI call ('ai_fill', minutes on the hosted provider)
-- never holds up reading: the stack runs one worker for reading and agents, and one for AI help.
-- Same body as app.claim_next_job (014, ordering from 016) with a step filter.

CREATE OR REPLACE FUNCTION app.claim_next_job_for_steps(p_stale_seconds integer, p_steps text[])
RETURNS TABLE(job_id uuid, tenant_id uuid, work_request_id uuid, step text, subject_id uuid,
              attempts integer, exhausted boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  picked uuid;
BEGIN
  SELECT j.id INTO picked
  FROM jobs j
  WHERE j.step = ANY(p_steps)
    AND ((j.status = 'queued' AND j.run_after <= now())
         OR (j.status = 'running' AND j.locked_at < now() - make_interval(secs => p_stale_seconds)))
  ORDER BY (j.step = 'ai_fill'), j.run_after
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF picked IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  WITH old AS (SELECT j.id, j.attempts AS prev FROM jobs j WHERE j.id = picked),
  upd AS (
    UPDATE jobs j
    SET status = 'running', locked_at = now(), attempts = LEAST(j.attempts + 1, 4)
    WHERE j.id = picked
    RETURNING j.id, j.tenant_id, j.work_request_id, j.step, j.subject_id, j.attempts
  )
  SELECT upd.id, upd.tenant_id, upd.work_request_id, upd.step, upd.subject_id, upd.attempts, (old.prev >= 4)
  FROM upd JOIN old ON old.id = upd.id;
END $$;

REVOKE ALL ON FUNCTION app.claim_next_job_for_steps(integer, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.claim_next_job_for_steps(integer, text[]) TO avenel_app;
