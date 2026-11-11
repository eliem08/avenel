"""Phase 2 completion: reading a real PDF, failing loudly, and serving page images.

Before Phase 2 completion, a missing native library made every real PDF "read" as garbage:
rendering and OCR caught the ImportError, decoded the PDF bytes as text, and returned an
empty extraction with status 200. These tests use real PDFs generated with PyMuPDF, run the
local OCR engine (no external provider, A.2.7), and check that failures are visible.
"""

from __future__ import annotations

import datetime
import hashlib
import uuid

import fitz  # type: ignore[import-untyped]
import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.clients.service import create_client_entity
from avenel.periods.service import open_accounting_period
from avenel.tenancy.auth import set_rls_context
from tests.helpers import seed_membership, seed_tenant, seed_user

LINES = [
    "Societe Atlas Fournitures SARL",
    "ICE: 001234567890123   IF: 12345678   RC 45678 Casablanca",
    "FACTURE N: FAC-2026-0412",
    "Date: 12/03/2026",
    "Client: Atlas Distribution SARL",
    "Total HT: 10 000,00 MAD",
    "TVA 20% Base: 10 000,00 Montant: 2 000,00",
    "Total TTC: 12 000,00 MAD",
]


def _pdf(scanned: bool = False) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 72
    for line in LINES + [f"Ref {uuid.uuid4().hex[:8]}"]:  # unique bytes per test (duplicate detection)
        page.insert_text((60, y), line, fontsize=11, fontname="helv")
        y += 20
    if scanned:
        pix = page.get_pixmap(dpi=150)
        out = fitz.open()
        p2 = out.new_page(width=595, height=842)
        p2.insert_image(p2.rect, pixmap=pix)
        return out.tobytes()
    return doc.tobytes()


def _h(sub: str | None, tenant: uuid.UUID | None = None) -> dict[str, str]:
    h = {"Idempotency-Key": str(uuid.uuid4())}
    if sub:
        h["Authorization"] = f"Bearer {sub}"
    if tenant:
        h["X-Tenant-Id"] = str(tenant)
    return h


@pytest.fixture
def env(db_conn: psycopg.Connection) -> dict:
    t = seed_tenant(db_conn, "Cabinet Lecture")
    sub = f"acc-{uuid.uuid4()}"
    uid = seed_user(db_conn, identity_subject=sub, email=f"{sub}@a.ma")
    seed_membership(db_conn, uid, t, "accountant")
    t2 = seed_tenant(db_conn, "Cabinet Autre")
    other = f"other-{uuid.uuid4()}"
    seed_membership(db_conn, seed_user(db_conn, identity_subject=other, email=f"{other}@b.ma"), t2, "accountant")
    set_rls_context(db_conn, t, uid)
    c = create_client_entity(db_conn, t, "Atlas Distribution SARL", str(uid), ice="001500000000001").id
    p = open_accounting_period(
        db_conn, t, c, str(uid), "2026-03", datetime.date(2026, 3, 1), datetime.date(2026, 3, 31), datetime.date(2026, 12, 31)
    )["id"]
    wr = uuid.uuid4()
    with db_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO work_requests (id, tenant_id, client_entity_id, accounting_period_id, service_code, status)
               VALUES (%s, %s, %s, %s, 'monthly_bookkeeping', 'intake');""",
            (wr, t, c, p),
        )
    db_conn.commit()
    return {"t": t, "sub": sub, "other": other, "wr": wr}


def _upload(client: TestClient, env: dict, data: bytes) -> str:
    r = client.post(
        f"/v1/work-requests/{env['wr']}/uploads",
        headers=_h(env["sub"], env["t"]),
        json={"original_filename": "facture.pdf", "byte_size": len(data), "mime_type": "application/pdf",
              "sha256": hashlib.sha256(data).hexdigest()},
    )
    assert r.status_code in (200, 201), r.text
    doc = r.json()["document_id"]
    put = client.put(f"/v1/documents/{doc}/content", content=data,
                     headers={**_h(env["sub"], env["t"]), "Content-Type": "application/octet-stream"})
    assert put.status_code == 200, put.text
    return doc


@pytest.mark.parametrize("scanned", [False, True], ids=["text-pdf", "scanned-pdf"])
def test_real_pdf_is_read_with_bboxes(env, scanned):
    c = TestClient(app)
    doc = _upload(c, env, _pdf(scanned))
    done = c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(env["sub"], env["t"]))
    assert done.status_code == 200, done.text
    assert done.json()["doc_type"] == "purchase_invoice"
    fields = c.get(f"/v1/documents/{doc}/extraction", headers=_h(env["sub"], env["t"])).json()["fields"]
    assert fields["invoice_number"]["value"] == "FAC-2026-0412"
    assert fields["supplier_ice"]["value"] == "001234567890123"
    assert float(fields["total_ttc"]["value"]) == 12000.0
    for k in ("invoice_number", "supplier_ice", "total_ttc"):
        x0, y0, x1, y1 = fields[k]["bbox"]
        assert 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0  # Part K 7: normalized bboxes

    img = c.get(f"/v1/documents/{doc}/pages/1/image", headers=_h(env["sub"], env["t"]))
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"
    assert img.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_page_image_scope_rules(env):
    c = TestClient(app)
    doc = _upload(c, env, _pdf())
    assert c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(env["sub"], env["t"])).status_code == 200
    assert c.get(f"/v1/documents/{doc}/pages/1/image", headers=_h(env["other"], env["t"])).status_code == 404
    assert c.get(f"/v1/documents/{doc}/pages/1/image", headers=_h(env["other"])).status_code == 404
    assert c.get(f"/v1/documents/{doc}/pages/9/image", headers=_h(env["sub"], env["t"])).status_code == 404
    assert c.get(f"/v1/documents/{doc}/pages/1/image", headers=_h(None)).status_code == 401


def test_unrenderable_pdf_fails_loudly(env, monkeypatch):
    """A real PDF that cannot be rendered must not be 'read' as text."""
    c = TestClient(app)
    doc = _upload(c, env, _pdf())

    def broken_open(*_a, **_k):
        raise RuntimeError("simulated missing native library")

    monkeypatch.setattr(fitz, "open", broken_open)
    r = c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(env["sub"], env["t"]))
    assert r.status_code == 422, r.text
    ex = c.get(f"/v1/documents/{doc}/extraction", headers=_h(env["sub"], env["t"]))
    assert ex.status_code == 404  # nothing half-written


def test_ocr_engine_unavailable_queues_the_reading_and_the_worker_finishes_it(env, monkeypatch, postgres_url, db_conn):
    """OCR down: the upload answers 202, a read_document job is queued, nothing is half-written.
    Once OCR is back the worker reads the document (ARCHITECTURE.md D.1; was a 503 before 11 Nov 2026)."""
    from avenel.jobs.worker import run_once
    from avenel.ocr import adapter

    db_conn.execute("UPDATE jobs SET status = 'failed', locked_at = NULL, finished_at = now() "
                    "WHERE status IN ('queued','running')")  # nothing else is due: the next job is this test's
    db_conn.commit()
    c = TestClient(app)
    doc = _upload(c, env, _pdf(scanned=True))
    with monkeypatch.context() as m:
        m.setattr(adapter.LocalOcrEngine, "_get_latin_ocr", lambda self: False)
        m.setattr(adapter.LocalOcrEngine, "_get_arabic_ocr", lambda self: False)
        r = c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(env["sub"], env["t"]))
        assert r.status_code == 202, r.text
        assert r.json() == {"document_id": doc, "status": "processing", "queued": True}
        assert c.get(f"/v1/documents/{doc}/extraction", headers=_h(env["sub"], env["t"])).status_code == 404
        job = db_conn.execute(
            "SELECT step, status, attempts FROM jobs WHERE tenant_id = %s AND subject_id = %s", (env["t"], doc)
        ).fetchone()
        assert job == ("read_document", "queued", 0)
        # The worker tries while OCR is still down: first attempt fails and is scheduled again, not lost.
        assert run_once(postgres_url) == "retry"
        db_conn.rollback()
        assert db_conn.execute(
            "SELECT status, attempts, run_after > now() FROM jobs WHERE tenant_id = %s AND subject_id = %s",
            (env["t"], doc),
        ).fetchone() == ("queued", 1, True)

    # OCR is back; the retry becomes due and the worker reads the document.
    db_conn.rollback()
    db_conn.execute("UPDATE jobs SET run_after = now() WHERE tenant_id = %s AND subject_id = %s", (env["t"], doc))
    db_conn.commit()
    assert run_once(postgres_url) == "succeeded"
    fields = c.get(f"/v1/documents/{doc}/extraction", headers=_h(env["sub"], env["t"])).json()["fields"]
    assert fields["invoice_number"]["value"] == "FAC-2026-0412"
    assert db_conn.execute(
        "SELECT status FROM jobs WHERE tenant_id = %s AND subject_id = %s", (env["t"], doc)
    ).fetchone() == ("succeeded",)
