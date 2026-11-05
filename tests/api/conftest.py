"""API tests connect the application exactly as production does (Part C.5).

The API's own database connection uses the `avenel_app` role (not owner, not
superuser, no BYPASSRLS), so forced RLS is exercised on every API request in
the suite. Before Phase 1 completion the API ran as a superuser in tests, which
hid an RLS bug that made every real login fail.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import psycopg
import pytest

from apps.api.deps import get_db
from apps.api.main import app


def _app_role_url(postgres_url: str) -> str:
    info = psycopg.conninfo.conninfo_to_dict(postgres_url)
    info["user"] = "avenel_app"
    info["password"] = os.environ.get("AVENEL_APP_PASSWORD", "avenel_app_secret")
    return psycopg.conninfo.make_conninfo(**info)


@pytest.fixture(autouse=True)
def api_uses_app_role(postgres_url: str) -> Generator[None, None, None]:
    url = _app_role_url(postgres_url)

    def _get_db() -> Generator[psycopg.Connection, None, None]:
        with psycopg.connect(url, autocommit=False) as conn:
            yield conn

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
