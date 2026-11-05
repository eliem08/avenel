"""Guard (Phase 1 completion): every DELETE/UPDATE statement in application code targets a
table on which avenel_app actually holds that privilege, and every table has SELECT.

Two production bugs (no DELETE on `issues`, no grant at all on `export_round_trips`) were
invisible because the API tests ran as a superuser. This test reads the real grants.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
STATEMENT = re.compile(r"\b(DELETE\s+FROM|UPDATE|INSERT\s+INTO)\s+([a-z_][a-z0-9_]*)\b", re.IGNORECASE)


def _app_code_statements() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for base in ("avenel", "apps"):
        for path in (ROOT / base).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for verb, table in STATEMENT.findall(text):
                verb_key = verb.split()[0].upper()
                if table.lower() in {"set", "of", "on"}:
                    continue
                found.add((verb_key, table.lower()))
    return found


def _privileges(conn: psycopg.Connection) -> tuple[set[str], set[tuple[str, str]]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
        )
        tables = {r[0] for r in cur.fetchall()}
        grants = set()
        for t in tables:
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                cur.execute("SELECT has_table_privilege('avenel_app', %s, %s);", (f"public.{t}", priv))
                if cur.fetchone()[0]:
                    grants.add((priv, t))
    return tables, grants


def test_every_write_in_app_code_is_granted_to_avenel_app(db_conn: psycopg.Connection) -> None:
    tables, grants = _privileges(db_conn)
    missing = sorted(
        f"{verb} {table}"
        for verb, table in _app_code_statements()
        if table in tables and (verb, table) not in grants
    )
    # Append-only tables (Part A.5) intentionally lack UPDATE/DELETE: code must not write them that way.
    assert missing == [], f"app code issues statements avenel_app may not run: {missing}"


def test_avenel_app_can_select_every_table_it_writes(db_conn: psycopg.Connection) -> None:
    tables, grants = _privileges(db_conn)
    written = {t for _, t in _app_code_statements() if t in tables}
    assert sorted(t for t in written if ("SELECT", t) not in grants) == []
