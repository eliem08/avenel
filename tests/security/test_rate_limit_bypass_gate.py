"""Phase 5: the rate-limit bypass header worked for any caller, production included."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.middleware import get_rate_limit_store


@pytest.fixture
def production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AVENEL_AUTH_TEST_MODE", raising=False)


def test_bypass_header_ignored_outside_test_mode(production_mode) -> None:
    get_rate_limit_store().reset()
    c = TestClient(app)
    codes = [
        c.get(f"/v1/documents/{uuid.uuid4()}", headers={"X-Test-Bypass-Rate-Limit": "true"}).status_code
        for _ in range(65)
    ]
    assert 429 in codes, "upload/document endpoints must stay rate limited (60/min) whatever the header"
    get_rate_limit_store().reset()
