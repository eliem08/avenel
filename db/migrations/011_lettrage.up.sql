-- 011_lettrage.up.sql
-- Phase 6b: lettrage of customer (342x) and supplier (441x) accounts.
-- Scope decision: founder, 7 Nov 2026 (docs/plans/phase-6.md, ARCHITECTURE.md B.3 and D.7b).
--
-- A lettrage group links debit lines and credit lines of the same account and counterparty.
-- Each link carries the amount allocated from that line, so partial settlements leave an open
-- balance on the line. Only lines of approved or exported proposals can be lettered: those lines
-- no longer change. Groups are never deleted; an accepted group is undone by status 'reversed'
-- (délettrage), with who, when and why.

ALTER TABLE journal_lines
  ADD CONSTRAINT journal_lines_tenant_client_id_key UNIQUE (tenant_id, client_entity_id, id);

CREATE TABLE lettrage_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  counterparty_id uuid NOT NULL,
  account_code text NOT NULL CHECK (account_code ~ '^(342|441)[0-9]*$'),
  status text NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed','accepted','rejected','superseded','reversed')),
  kind text NOT NULL CHECK (kind IN ('exact','grouped','split','partial','manual')),
  letter_code text CHECK (letter_code ~ '^[A-Z]{1,4}$'),
  total_mad numeric(18,2) NOT NULL CHECK (total_mad > 0),
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  proposed_by text NOT NULL CHECK (proposed_by IN ('rules','human')),
  decided_by uuid REFERENCES users(id),
  decided_at timestamptz,
  reversed_by uuid REFERENCES users(id),
  reversed_at timestamptz,
  reversal_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, counterparty_id)
    REFERENCES counterparties(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  CHECK ((status IN ('accepted','reversed')) = (letter_code IS NOT NULL)),
  CHECK ((status IN ('accepted','rejected','reversed')) = (decided_at IS NOT NULL)),
  CHECK ((status = 'reversed') = (reversed_at IS NOT NULL)),
  CHECK (status <> 'reversed' OR (reversal_reason IS NOT NULL AND length(trim(reversal_reason)) > 0))
);
CREATE UNIQUE INDEX lettrage_letter_unique
  ON lettrage_groups (tenant_id, client_entity_id, account_code, letter_code)
  WHERE letter_code IS NOT NULL;
CREATE INDEX lettrage_groups_by_client ON lettrage_groups (tenant_id, client_entity_id, status);

CREATE TABLE lettrage_allocations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  group_id uuid NOT NULL,
  journal_line_id uuid NOT NULL,
  side text NOT NULL CHECK (side IN ('debit','credit')),
  amount_mad numeric(18,2) NOT NULL CHECK (amount_mad > 0),
  FOREIGN KEY (tenant_id, client_entity_id, group_id)
    REFERENCES lettrage_groups(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, journal_line_id)
    REFERENCES journal_lines(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, group_id, journal_line_id)
);
CREATE INDEX lettrage_allocations_by_line ON lettrage_allocations (tenant_id, journal_line_id);

-- Allocations are written once with their group and never change.
CREATE TRIGGER lettrage_allocations_no_mutation BEFORE UPDATE OR DELETE ON lettrage_allocations
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- Status transitions, balance and over-allocation are enforced by the database, not only by code.
CREATE OR REPLACE FUNCTION app.lettrage_group_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_debit numeric(18,2);
  v_credit numeric(18,2);
  v_bad int;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'lettrage_groups are never deleted' USING ERRCODE = '42501';
  END IF;
  IF NEW.tenant_id <> OLD.tenant_id OR NEW.client_entity_id <> OLD.client_entity_id
     OR NEW.counterparty_id <> OLD.counterparty_id OR NEW.account_code <> OLD.account_code
     OR NEW.total_mad <> OLD.total_mad OR NEW.kind <> OLD.kind THEN
    RAISE EXCEPTION 'lettrage group content is immutable' USING ERRCODE = '42501';
  END IF;
  IF NEW.status = OLD.status THEN
    IF NEW IS DISTINCT FROM OLD THEN
      RAISE EXCEPTION 'lettrage group % is immutable in status %', OLD.id, OLD.status USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
  END IF;
  IF NOT ((OLD.status = 'proposed' AND NEW.status IN ('accepted','rejected','superseded'))
          OR (OLD.status = 'accepted' AND NEW.status = 'reversed')) THEN
    RAISE EXCEPTION 'lettrage status % -> % not allowed', OLD.status, NEW.status USING ERRCODE = '42501';
  END IF;
  IF NEW.status = 'accepted' THEN
    -- Serialise acceptances on the same lines.
    PERFORM 1 FROM journal_lines jl
      JOIN lettrage_allocations a ON a.journal_line_id = jl.id AND a.tenant_id = jl.tenant_id
      WHERE a.tenant_id = NEW.tenant_id AND a.group_id = NEW.id
      FOR UPDATE OF jl;
    SELECT coalesce(sum(amount_mad) FILTER (WHERE side = 'debit'), 0),
           coalesce(sum(amount_mad) FILTER (WHERE side = 'credit'), 0)
      INTO v_debit, v_credit
      FROM lettrage_allocations WHERE tenant_id = NEW.tenant_id AND group_id = NEW.id;
    IF v_debit <> v_credit OR v_debit <> NEW.total_mad THEN
      RAISE EXCEPTION 'lettrage group % is not balanced (debit %, credit %)', NEW.id, v_debit, v_credit
        USING ERRCODE = '23514';
    END IF;
    SELECT count(*) INTO v_bad
      FROM lettrage_allocations a
      JOIN journal_lines jl ON jl.id = a.journal_line_id AND jl.tenant_id = a.tenant_id
      JOIN journal_proposals jp ON jp.id = jl.journal_proposal_id AND jp.tenant_id = jl.tenant_id
      WHERE a.tenant_id = NEW.tenant_id AND a.group_id = NEW.id
        AND (jp.status NOT IN ('approved','exported')
             OR jl.account_code <> NEW.account_code
             OR jl.counterparty_id IS DISTINCT FROM NEW.counterparty_id
             OR (a.side = 'debit') <> (jl.debit_mad > 0)
             OR a.amount_mad > (CASE WHEN a.side = 'debit' THEN jl.debit_mad ELSE jl.credit_mad END)
                 - coalesce((SELECT sum(o.amount_mad) FROM lettrage_allocations o
                             JOIN lettrage_groups g ON g.id = o.group_id AND g.tenant_id = o.tenant_id
                             WHERE o.tenant_id = a.tenant_id AND o.journal_line_id = a.journal_line_id
                               AND g.status = 'accepted' AND g.id <> NEW.id), 0));
    IF v_bad > 0 THEN
      RAISE EXCEPTION 'lettrage group % allocates more than the open balance or an unapproved line', NEW.id
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER lettrage_groups_guard BEFORE UPDATE OR DELETE ON lettrage_groups
  FOR EACH ROW EXECUTE FUNCTION app.lettrage_group_guard();

ALTER TABLE lettrage_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE lettrage_groups FORCE ROW LEVEL SECURITY;
CREATE POLICY lettrage_groups_tenant ON lettrage_groups
  USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant());
ALTER TABLE lettrage_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE lettrage_allocations FORCE ROW LEVEL SECURITY;
CREATE POLICY lettrage_allocations_tenant ON lettrage_allocations
  USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant());

GRANT SELECT, INSERT, UPDATE ON lettrage_groups TO avenel_app;
GRANT SELECT, INSERT ON lettrage_allocations TO avenel_app;
