-- 016_document_ocr_and_ai_fill.up.sql
-- Reading no longer waits for the AI provider (docs/plans/phase-8a-orchestrator.md, "AI in its own job").
-- The worker keeps the OCR result of each document version, so the separate 'ai_fill' job can ask the
-- provider for the fields still empty without running OCR again.

CREATE TABLE document_ocr (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  document_version_id uuid NOT NULL,
  engine text NOT NULL,
  engine_version text NOT NULL,
  page_count integer NOT NULL CHECK (page_count >= 0),
  full_text text NOT NULL,
  lines jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, document_version_id) REFERENCES document_versions(tenant_id, id),
  UNIQUE (tenant_id, document_version_id)
);

ALTER TABLE document_ocr ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_ocr FORCE ROW LEVEL SECURITY;
CREATE POLICY document_ocr_tenant ON document_ocr
  USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant());

-- Append-only, like extractions: what OCR read is evidence.
GRANT SELECT, INSERT ON document_ocr TO avenel_app;

ALTER TABLE jobs DROP CONSTRAINT jobs_step_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_step_check
  CHECK (step IN ('read_document', 'ai_fill', 'prepare_proposals', 'reconcile'));

-- Reading jobs before AI jobs: a person waits for a document to be read, not for the AI suggestions.
-- Same function as 014 except the ORDER BY.
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
  ORDER BY (j.step = 'ai_fill'), j.run_after  -- reading first: AI help may wait (016)
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
