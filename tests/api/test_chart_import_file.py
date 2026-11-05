"""POST /v1/client-entities/{id}/chart-accounts/import-file (Phase 1 completion).

Four quadrants as in test_phase1_matrix.py (same tenant 200, cross tenant 404, client_user
out of scope 404, unauthenticated 401), plus format handling through the hardened parsers.
The API runs as avenel_app in this suite (tests/api/conftest.py).
"""

from __future__ import annotations

import io
import uuid
import zipfile

from fastapi.testclient import TestClient
from openpyxl import Workbook

from apps.api.main import app
from tests.api.test_phase1_matrix import matrix_env  # noqa: F401  (pytest fixture)

CSV = "code;label\n34211;Clients divers\n44111;Fournisseurs divers\n".encode()


def _url(cid) -> str:
    return f"/v1/client-entities/{cid}/chart-accounts/import-file"


def _headers(sub: str | None, tenant=None) -> dict[str, str]:
    h = {"Idempotency-Key": str(uuid.uuid4())}
    if sub:
        h["X-Identity-Subject"] = sub
    if tenant:
        h["X-Tenant-Id"] = str(tenant)
    return h


def _post(client: TestClient, url: str, headers: dict, name: str = "plan.csv", data: bytes = CSV):
    return client.post(url, headers=headers, files={"file": (name, data, "application/octet-stream")})


def test_import_file_four_quadrants(matrix_env):  # noqa: F811
    c = TestClient(app)
    e = matrix_env
    ok = _post(c, _url(e["c1a_id"]), _headers(e["u1_sub"], e["t1_id"]))
    assert ok.status_code == 200, ok.text
    assert ok.json()["imported_count"] == 2

    assert _post(c, _url(e["c1a_id"]), _headers(e["u2_sub"], e["t1_id"])).status_code == 404
    assert _post(c, _url(e["c1a_id"]), _headers(e["u2_sub"])).status_code == 404
    assert _post(c, _url(e["c1b_id"]), _headers(e["cu_sub"], e["t1_id"])).status_code == 404
    assert _post(c, _url(e["c1a_id"]), _headers(None)).status_code == 401
    assert _post(c, _url(uuid.uuid4()), _headers(e["u1_sub"], e["t1_id"])).status_code == 404


def test_import_file_xlsx(matrix_env):  # noqa: F811
    wb = Workbook()
    ws = wb.active
    ws.append(["code", "label"])
    ws.append(["61111", "Achats de marchandises"])
    buf = io.BytesIO()
    wb.save(buf)
    e = matrix_env
    r = _post(TestClient(app), _url(e["c1a_id"]), _headers(e["u1_sub"], e["t1_id"]), "plan.xlsx", buf.getvalue())
    assert r.status_code == 200, r.text
    assert r.json()["imported_count"] == 1


def test_import_file_rejects_other_formats(matrix_env):  # noqa: F811
    e = matrix_env
    r = _post(TestClient(app), _url(e["c1a_id"]), _headers(e["u1_sub"], e["t1_id"]), "plan.pdf", b"%PDF-1.4")
    assert r.status_code == 415


def test_import_file_rejects_corrupt_xlsx(matrix_env):  # noqa: F811
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>')
    e = matrix_env
    r = _post(TestClient(app), _url(e["c1a_id"]), _headers(e["u1_sub"], e["t1_id"]), "plan.xlsx", buf.getvalue())
    assert r.status_code == 422, r.text
