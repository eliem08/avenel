"""Phase 3 completion: a document read by the real OCR pipeline can become a proposal.

Before Phase 3 completion, generating a proposal for any document read from a real PDF
crashed inside the generator ("'list' object has no attribute 'get'") and the route
reported the crash as 422. Proposal tests only used hand-built field dictionaries.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from apps.api.main import app
from tests.api.test_document_reading_real_pdf import _h, _pdf, _upload, env  # noqa: F401


def _read(client: TestClient, env: dict) -> str:  # noqa: F811
    doc = _upload(client, env, _pdf(scanned=True))
    r = client.post(f"/v1/documents/{doc}:complete-upload", headers=_h(env["sub"], env["t"]))
    assert r.status_code == 200, r.text
    return doc


def test_generate_on_real_read_document_does_not_crash(env):  # noqa: F811
    c = TestClient(app)
    doc = _read(c, env)
    r = c.post(f"/v1/documents/{doc}:generate-proposal", headers=_h(env["sub"], env["t"]))
    assert r.status_code == 200, r.text
    body = r.json()
    # No approved tax mapping exists for this new client: the generator must block with
    # ACCOUNT_UNMAPPED (Part K 15) and create no lines, not crash.
    assert body["status"] == "blocked", body
    assert body["issue_code"] == "ACCOUNT_UNMAPPED", body
    assert body["lines"] == []


def test_generate_unknown_document_is_404(env):  # noqa: F811
    c = TestClient(app)
    r = c.post(f"/v1/documents/{uuid.uuid4()}:generate-proposal", headers=_h(env["sub"], env["t"]))
    assert r.status_code == 404
