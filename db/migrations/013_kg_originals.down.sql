-- 013_kg_originals.down.sql
DELETE FROM kg_edges WHERE to_node IN (SELECT id FROM kg_nodes WHERE kind = 'finance_law');
DELETE FROM kg_nodes WHERE kind = 'finance_law';
ALTER TABLE kg_nodes DROP CONSTRAINT kg_nodes_kind_check;
ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_kind_check CHECK (kind IN
  ('source','document','law','decree','dahir','circular','bo_issue','article','pack_rule'));
DROP TABLE IF EXISTS kg_originals;
