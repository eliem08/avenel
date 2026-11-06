-- 011_lettrage.down.sql
DROP TABLE IF EXISTS lettrage_allocations;
DROP TABLE IF EXISTS lettrage_groups;
DROP FUNCTION IF EXISTS app.lettrage_group_guard();
ALTER TABLE journal_lines DROP CONSTRAINT IF EXISTS journal_lines_tenant_client_id_key;
