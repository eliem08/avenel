-- 012_knowledge_graph.up.sql
-- Phase 7a: public legal and accounting texts collected by the crawler, and the reference graph built
-- from them. Global data (public texts), no tenant_id. The application role may read and insert,
-- never update or delete (documents are append-only). Evidence for experts, never a rule source.

CREATE TABLE kg_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_code text NOT NULL CHECK (source_code ~ '^[a-z_]+$'),
  url text NOT NULL CHECK (url ~ '^https://'),
  fetched_at timestamptz NOT NULL DEFAULT now(),
  http_status integer NOT NULL,
  content_type text NOT NULL,
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  title text,
  text_content text NOT NULL,
  UNIQUE (url, sha256)
);

CREATE TRIGGER kg_documents_append_only
  BEFORE UPDATE OR DELETE ON kg_documents
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

CREATE TABLE kg_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL CHECK (kind IN
    ('source','document','law','decree','dahir','circular','bo_issue','article','pack_rule')),
  key text NOT NULL,
  label text NOT NULL,
  UNIQUE (kind, key)
);

CREATE TABLE kg_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  from_node uuid NOT NULL REFERENCES kg_nodes(id),
  to_node uuid NOT NULL REFERENCES kg_nodes(id),
  kind text NOT NULL CHECK (kind IN ('published_by','mentions','cites_source')),
  document_id uuid REFERENCES kg_documents(id),
  evidence text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (from_node, to_node, kind, document_id)
);

CREATE INDEX kg_edges_to ON kg_edges (to_node, kind);

GRANT SELECT, INSERT ON kg_documents, kg_nodes, kg_edges TO avenel_app;
