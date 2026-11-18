-- 015_agent_tasks.up.sql
-- Phase 8a (docs/plans/phase-8a-orchestrator.md): the orchestrator hands work between agents through the
-- job queue. New steps for the bookkeeping and reconciliation agents, and an append-only record of
-- every agent task and handoff.

ALTER TABLE jobs DROP CONSTRAINT jobs_step_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_step_check
  CHECK (step IN ('read_document', 'prepare_proposals', 'reconcile'));

CREATE TABLE agent_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  work_request_id uuid NOT NULL,
  agent text NOT NULL CHECK (agent IN ('document', 'bookkeeping', 'reconciliation', 'orchestrator')),
  step text NOT NULL,
  job_id uuid REFERENCES jobs(id),
  subject_id uuid,
  outcome text NOT NULL CHECK (outcome IN ('done', 'handed_off', 'escalated', 'ready_for_review')),
  handed_off_to text CHECK (handed_off_to IN ('document', 'bookkeeping', 'reconciliation', 'human')),
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, work_request_id) REFERENCES work_requests(tenant_id, id)
);
CREATE INDEX agent_tasks_work_request ON agent_tasks (tenant_id, work_request_id, created_at);

ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY agent_tasks_tenant ON agent_tasks
  USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant());

-- Append-only: a recorded task is evidence of what an agent did (Part A rule 5).
GRANT SELECT, INSERT ON agent_tasks TO avenel_app;
