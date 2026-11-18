-- 016_document_ocr_and_ai_fill.down.sql
DELETE FROM jobs WHERE step = 'ai_fill';
ALTER TABLE jobs DROP CONSTRAINT jobs_step_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_step_check CHECK (step IN ('read_document', 'prepare_proposals', 'reconcile'));
DROP TABLE IF EXISTS document_ocr;

-- Restore the 014 ordering.
CREATE OR REPLACE FUNCTION app.claim_next_job(p_stale_seconds integer)
RETURNS TABLE(job_id uuid, tenant_id uuid, work_request_id uuid, step text, subject_id uuid,
              attempts integer, exhausted boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  picked uuid;
BEGIN
  SELECT j.id INTO picked
  FROM jobs j
  WHERE (j.status = 'queued' AND j.run_after <= now())
     OR (j.status = 'running' AND j.locked_at < now() - make_interval(secs => p_stale_seconds))
  ORDER BY j.run_after
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
