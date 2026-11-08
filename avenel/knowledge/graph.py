"""Storage and graph building for the legal knowledge graph (migration 012).

Runs as avenel_app (SELECT and INSERT only on these tables). Documents are append-only: the same URL with the same
hash is stored once; a changed text is a new row. Edges point at the document that shows them.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

import psycopg

from avenel.infrastructure.storage import StorageBackend, get_storage
from avenel.jurisdiction.loader import JurisdictionPackLoader
from avenel.knowledge.crawler import CrawledDocument
from avenel.knowledge.extract import cgi_article_of, extract_references
from avenel.knowledge.sources import SOURCES


def _node(cur: psycopg.Cursor[Any], kind: str, key: str, label: str) -> uuid.UUID:
    cur.execute(
        "INSERT INTO kg_nodes (kind, key, label) VALUES (%s, %s, %s) ON CONFLICT (kind, key) DO NOTHING",
        (kind, key, label),
    )
    cur.execute("SELECT id FROM kg_nodes WHERE kind = %s AND key = %s", (kind, key))
    row = cur.fetchone()
    assert row is not None
    return uuid.UUID(str(row[0]))


def _edge(
    cur: psycopg.Cursor[Any], a: uuid.UUID, b: uuid.UUID, kind: str,
    document_id: uuid.UUID | None, evidence: str | None,
) -> None:
    cur.execute(
        """INSERT INTO kg_edges (from_node, to_node, kind, document_id, evidence)
           VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
        (a, b, kind, document_id, evidence),
    )


def original_key(sha256: str) -> str:
    return f"kg/{sha256[:2]}/{sha256}"


def store_document(
    conn: psycopg.Connection[Any], doc: CrawledDocument, storage: StorageBackend | None = None,
) -> tuple[uuid.UUID, bool]:
    """Insert the document and its reference edges. Returns (id, created)."""
    with conn.cursor() as cur:
        if doc.original:  # exact bytes, kept forever; also back-fills documents stored before migration 013
            cur.execute("SELECT 1 FROM kg_originals WHERE sha256 = %s", (doc.sha256,))
            if cur.fetchone() is None:
                key = original_key(doc.sha256)
                (storage or get_storage()).put_original(key, doc.original, doc.content_type)
                cur.execute(
                    """INSERT INTO kg_originals (sha256, content_type, byte_size, storage_key)
                       VALUES (%s, %s, %s, %s) ON CONFLICT (sha256) DO NOTHING""",
                    (doc.sha256, doc.content_type, len(doc.original), key),
                )
        cur.execute("SELECT id FROM kg_documents WHERE url = %s AND sha256 = %s", (doc.url, doc.sha256))
        row = cur.fetchone()
        if row is not None:
            return uuid.UUID(str(row[0])), False
        cur.execute(
            """INSERT INTO kg_documents (source_code, url, http_status, content_type, sha256, title, text_content)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (doc.source_code, doc.url, doc.status, doc.content_type, doc.sha256, doc.title, doc.text),
        )
        inserted = cur.fetchone()
        assert inserted is not None
        doc_id = uuid.UUID(str(inserted[0]))
        label = next((s.label for s in SOURCES if s.code == doc.source_code), doc.source_code)
        src = _node(cur, "source", doc.source_code, label)
        dnode = _node(cur, "document", doc.url, doc.title or doc.url)
        _edge(cur, dnode, src, "published_by", doc_id, None)
        _mentions(cur, dnode, doc_id, doc.url, doc.text)
    return doc_id, True


def _mentions(cur: psycopg.Cursor[Any], dnode: uuid.UUID, doc_id: uuid.UUID, url: str, text: str) -> None:
    for ref in extract_references(url.rsplit("/", 1)[-1] + "\n" + text):
        _edge(cur, dnode, _node(cur, ref.kind, ref.key, ref.label), "mentions", doc_id, ref.evidence)


def rebuild_mentions(conn: psycopg.Connection[Any]) -> int:
    """Re-read every stored document with the current extractor; existing edges are kept."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, url, text_content FROM kg_documents")
        rows = cur.fetchall()
        for doc_id, url, text in rows:
            cur.execute("SELECT id FROM kg_nodes WHERE kind = 'document' AND key = %s", (url,))
            found = cur.fetchone()
            if found is not None:
                _mentions(cur, uuid.UUID(str(found[0])), uuid.UUID(str(doc_id)), str(url), str(text))
    return len(rows)


def link_pack(conn: psycopg.Connection[Any], pack: JurisdictionPackLoader) -> int:
    """pack_rule -> cites_source -> article, for every rule whose source names a CGI article."""
    n = 0
    with conn.cursor() as cur:
        for key, rule in sorted(pack.rules.items()):
            article = cgi_article_of(str(rule.get("source", "")))
            if article is None:
                continue
            r = _node(cur, "pack_rule", key, f"{key} ({rule.get('status')})")
            a = _node(cur, "article", article, article)
            _edge(cur, r, a, "cites_source", None, str(rule.get("source")))
            n += 1
    return n


def evidence_for_rule(conn: psycopg.Connection[Any], rule_key: str) -> list[dict[str, Any]]:
    """Crawled documents that mention the article a pack rule cites (read-only, works as avenel_app)."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT a.key, d.url, d.title, d.fetched_at, m.evidence
                 FROM kg_nodes r
                 JOIN kg_edges c ON c.from_node = r.id AND c.kind = 'cites_source'
                 JOIN kg_nodes a ON a.id = c.to_node
                 JOIN kg_edges m ON m.to_node = a.id AND m.kind = 'mentions'
                 JOIN kg_documents d ON d.id = m.document_id
                WHERE r.kind = 'pack_rule' AND r.key = %s
                ORDER BY d.fetched_at DESC""",
            (rule_key,),
        )
        cols = [c.name for c in cur.description or []]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def store_all(conn: psycopg.Connection[Any], docs: Iterable[CrawledDocument]) -> tuple[int, int]:
    created = skipped = 0
    for doc in docs:
        _, new = store_document(conn, doc)
        conn.commit()
        created, skipped = (created + 1, skipped) if new else (created, skipped + 1)
    return created, skipped
