-- 013_kg_originals.up.sql
-- Founder rule, 8 Nov 2026: the knowledge graph forgets nothing. The exact bytes of every fetched file
-- (PDF or rendered page) are kept in object storage (C.2), under the global prefix kg/ (public texts,
-- not tenant data), and recorded here by SHA-256 so a document can always be re-read with a better
-- extractor. Insert-only for the app role; rows can never be changed or deleted.

CREATE TABLE kg_originals (
  sha256 text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  content_type text NOT NULL,
  byte_size bigint NOT NULL CHECK (byte_size >= 0),
  storage_key text NOT NULL UNIQUE CHECK (storage_key = 'kg/' || substr(sha256, 1, 2) || '/' || sha256),
  stored_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER kg_originals_append_only
  BEFORE UPDATE OR DELETE ON kg_originals
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

GRANT SELECT, INSERT ON kg_originals TO avenel_app;

-- Finance laws get their own node kind (key: year, or year-rectificative), so every finance law since
-- the first one is a single lookup.
ALTER TABLE kg_nodes DROP CONSTRAINT kg_nodes_kind_check;
ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_kind_check CHECK (kind IN
  ('source','document','law','finance_law','decree','dahir','circular','bo_issue','article','pack_rule'));
