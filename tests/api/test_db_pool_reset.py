"""B-07: a pooled connection must not carry one request's firm or user into the next (RLS context is
session-level). Runs against the real test database, no stub."""

from __future__ import annotations

import uuid

import pytest

from apps.api import deps


@pytest.fixture
def one_conn_pool(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AVENEL_DB_POOL_MIN", "1")
    monkeypatch.setenv("AVENEL_DB_POOL_MAX", "1")  # forces reuse of the same physical connection
    deps.close_pool()
    yield deps.get_pool()
    deps.close_pool()


def _ctx(conn) -> tuple[str, str, int]:
    row = conn.execute(
        "SELECT current_setting('app.tenant_id', true), current_setting('app.user_id', true), pg_backend_pid();"
    ).fetchone()
    return row[0] or "", row[1] or "", row[2]


def test_tenant_context_does_not_survive_return_to_pool(one_conn_pool):
    tenant, user = str(uuid.uuid4()), str(uuid.uuid4())
    with one_conn_pool.connection() as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false), set_config('app.user_id', %s, false);",
                     (tenant, user))
        assert _ctx(conn)[:2] == (tenant, user)
        pid = _ctx(conn)[2]
    with one_conn_pool.connection() as conn:
        t, u, pid2 = _ctx(conn)
    assert pid2 == pid  # same connection reused
    assert (t, u) == ("", "")


def test_context_is_cleared_even_after_a_failed_request(one_conn_pool):
    with pytest.raises(RuntimeError), one_conn_pool.connection() as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false);", (str(uuid.uuid4()),))
        raise RuntimeError("request failed")
    with one_conn_pool.connection() as conn:
        assert _ctx(conn)[:2] == ("", "")


def test_get_db_dependency_returns_a_clean_connection_to_the_pool(one_conn_pool):
    gen = deps.get_db()  # driven the way FastAPI drives it on a successful request
    conn = next(gen)
    conn.execute("SELECT set_config('app.tenant_id', %s, false);", (str(uuid.uuid4()),))
    with pytest.raises(StopIteration):
        next(gen)
    with one_conn_pool.connection() as again:
        assert again is conn
        assert _ctx(again)[:2] == ("", "")
