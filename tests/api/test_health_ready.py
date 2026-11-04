"""Regression test (Phase 5c-1): /health/ready returned 500 on every call.

`with next(get_db()) as conn` let the temporary generator be collected, which
closed the connection before the cursor opened. Found when the docker-compose
healthcheck never turned green.
"""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from apps.api.main import app


def test_health_ready_reports_database_ok(db_conn: psycopg.Connection) -> None:
    r = TestClient(app).get("/health/ready")
    assert r.status_code == 200, r.text
    assert r.json()["database"] == "ok"


def test_health_ready_returns_503_when_database_unreachable(db_conn: psycopg.Connection, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1")
    r = TestClient(app).get("/health/ready")
    assert r.status_code == 503, r.text
