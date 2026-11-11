-- 014_jobs.up.sql
-- Durable job queue (ARCHITECTURE.md C.1, D.1; plan docs/plans/b-01-job-queue.md).
-- A job is keyed by (work_request_id, step, subject_id, revision). At most 4 attempts, then the worker
-- marks it failed and opens an INTEGRATION_FAILURE issue.

CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  work_request_id uuid NOT NULL,
  step text NOT NULL CHECK (step IN ('read_document')),
  subject_id uuid NOT NULL,
  revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 4),
  run_after timestamptz NOT NULL DEFAULT now(),
  locked_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  FOREIGN KEY (tenant_id, work_request_id) REFERENCES work_requests(tenant_id, id),
  UNIQUE (tenant_id, work_request_id, step, subject_id, revision),
  CHECK ((status IN ('succeeded','failed')) = (finished_at IS NOT NULL)),
  CHECK ((status = 'running') = (locked_at IS NOT NULL))
);

-- One active job per subject and step.
CREATE UNIQUE INDEX jobs_one_active ON jobs (tenant_id, step, subject_id) WHERE status IN ('queued','running');
CREATE INDEX jobs_due ON jobs (run_after) WHERE status = 'queued';

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY jobs_tenant ON jobs
  USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant());

GRANT SELECT, INSERT, UPDATE ON jobs TO avenel_app;

-- The worker has no tenant context until it holds a job, so the next due job is picked by a
-- SECURITY DEFINER function (same pattern as app.resolve_membership). It returns identifiers only.
-- A job left 'running' longer than p_stale_seconds (crashed worker) is taken again. When such a job has
-- already used its 4 attempts it is returned with exhausted = true and attempts unchanged.
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

REVOKE ALL ON FUNCTION app.claim_next_job(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.claim_next_job(integer) TO avenel_app;
