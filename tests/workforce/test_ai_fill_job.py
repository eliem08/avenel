"""AI help in its own job (migration 016): reading finishes without waiting for the AI provider; the
'ai_fill' job then fills only empty fields in a new extraction, with evidence, and the file is handed to the
bookkeeping agent only after it. No network: the provider is a fake router."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from avenel.extraction import ai_fill
from avenel.extraction.router import ProviderCallResponse
from avenel.ocr.adapter import OcrLine, OcrResult
from avenel.workforce import orchestrator
from tests.api.test_document_reading_real_pdf import _h, _pdf, _upload, env  # noqa: F401
from tests.reconciliation.test_reconciliation import recon_test_env  # noqa: F401
from tests.workforce.test_orchestrator import (
    INVOICE,
    _job,
    _queued,
    _read_document,
    _tasks,
)

OCR = OcrResult(
    full_text="ATLAS FOURNITURES SARL\nFacture FA-2026-801\nTotal TTC 12 000,00",
    page_count=1,
    lines=[OcrLine(text="ATLAS FOURNITURES SARL", confidence=0.9, page=1, bbox=[0.1, 0.1, 0.5, 0.15], words=[]),
           OcrLine(text="Facture FA-2026-801", confidence=0.9, page=1, bbox=[0.1, 0.2, 0.5, 0.25], words=[]),
           OcrLine(text="Total TTC 12 000,00", confidence=0.9, page=1, bbox=[0.1, 0.3, 0.5, 0.35], words=[])],
    words=[],
)


class FakeRouter:
    def __init__(self, answer: dict) -> None:
        self.answer, self.calls = answer, 0

    def execute_call(self, tenant_id, policy, request, handler=None):
        self.calls += 1
        return ProviderCallResponse(None, "succeeded", self.answer, {}, 0.0)


def _with_ocr(conn: psycopg.Connection, env: dict, fields: dict) -> uuid.UUID:  # noqa: F811
    doc = _read_document(conn, env, fields)
    version = conn.execute("SELECT id FROM document_versions WHERE document_id = %s;", (doc,)).fetchone()[0]
    ai_fill.save_document_ocr(conn, env["tenant_id"], version, OCR)
    return doc


def _extractions(conn: psycopg.Connection, doc: uuid.UUID) -> list[tuple]:
    return conn.execute(
        "SELECT e.engine, e.fields FROM extractions e JOIN document_versions dv ON dv.id = e.document_version_id "
        "WHERE dv.document_id = %s ORDER BY e.created_at;", (doc,)
    ).fetchall()


@pytest.fixture(autouse=True)
def _ai_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-not-a-key")
    monkeypatch.setattr(ai_fill, "_tenant_policy", lambda conn, t: "GLOBAL_ALLOWED")


def test_ai_job_writes_a_new_extraction_with_evidence_and_keeps_a_persons_value(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env  # noqa: F811
    fields = {k: {"value": v["value"], "confidence": 0.97, "page": 1, "bbox": None} for k, v in INVOICE.items()}
    fields["supplier_name"] = {"value": None, "confidence": 0.0, "page": 1, "bbox": None}
    fields["client_name"] = {"value": "Saisi par une personne", "confidence": 1.0, "page": 1, "bbox": None}
    doc = _with_ocr(db_conn, env, fields)

    router = FakeRouter({"supplier_name": "ATLAS FOURNITURES SARL", "client_name": "AUTRE"})
    out = ai_fill.fill_document_in_background(db_conn, env["tenant_id"], doc, router=router)
    assert out == {"status": "succeeded", "filled": ["supplier_name"]}

    rows = _extractions(db_conn, doc)
    assert [r[0] for r in rows] == ["paddleocr", "ai_fill"]  # the first reading is kept, a new row is added
    latest = rows[-1][1]
    assert latest["supplier_name"]["value"] == "ATLAS FOURNITURES SARL"
    assert (latest["supplier_name"]["confidence"], latest["supplier_name"]["source"]) == (ai_fill.AI_REVIEW_CONFIDENCE, "ai")
    assert latest["client_name"]["value"] == "Saisi par une personne"
    evidence = db_conn.execute(
        "SELECT payload FROM evidence_records WHERE kind = 'ai_fill' AND work_request_id = %s;", (env["work_request_id"],)
    ).fetchone()[0]
    assert evidence["fields_filled"] == ["supplier_name"]


def test_nothing_filled_means_no_new_extraction(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env  # noqa: F811
    fields = {k: {"value": v["value"], "confidence": 0.97, "page": 1, "bbox": None} for k, v in INVOICE.items()}
    fields["supplier_name"] = {"value": None, "confidence": 0.0, "page": 1, "bbox": None}
    doc = _with_ocr(db_conn, env, fields)
    out = ai_fill.fill_document_in_background(db_conn, env["tenant_id"], doc, router=FakeRouter({"supplier_name": None}))
    assert out["filled"] == []
    assert len(_extractions(db_conn, doc)) == 1


def test_handoff_waits_for_the_documents_ai_job_then_happens_after_it(db_conn, recon_test_env):  # noqa: F811
    env = recon_test_env  # noqa: F811
    doc = _read_document(db_conn, env)
    # Reading of `doc` finished and queued its AI job: the file is not handed to bookkeeping yet.
    ai_job = db_conn.execute(
        "INSERT INTO jobs (tenant_id, work_request_id, step, subject_id) VALUES (%s, %s, 'ai_fill', %s) RETURNING id;",
        (env["tenant_id"], env["work_request_id"], doc),
    ).fetchone()[0]
    orchestrator.after_step(db_conn, _job(env, "read_document", doc, db_conn), {"ai_fill_queued": True})
    assert "prepare_proposals" not in _queued(db_conn, env)

    # The AI job finishes: now the document agent hands off.
    db_conn.execute("UPDATE jobs SET status = 'succeeded', finished_at = now() WHERE id = %s;", (ai_job,))
    orchestrator.after_step(db_conn, _job(env, "ai_fill", doc, db_conn), {"status": "succeeded", "filled": []})
    assert _queued(db_conn, env)[-1] == "prepare_proposals"
    assert _tasks(db_conn, env)[-1] == ("document", "ai_fill", "handed_off", "bookkeeping")


def test_worker_reading_does_not_call_the_ai_and_queues_the_ai_job(env, monkeypatch, postgres_url, db_conn):  # noqa: F811
    from avenel.jobs.worker import run_once

    db_conn.execute("UPDATE jobs SET status = 'failed', locked_at = NULL, finished_at = now() "
                    "WHERE status IN ('queued','running')")
    db_conn.commit()
    monkeypatch.setenv("AVENEL_READ_IN_BACKGROUND", "1")
    called: list[int] = []
    monkeypatch.setattr(ai_fill, "fill_missing_fields", lambda *a, **k: called.append(1) or
                        {"status": "succeeded", "filled": [], "provider_call_id": None})
    c = TestClient(app)
    doc = _upload(c, env, _pdf(scanned=False))
    assert c.post(f"/v1/documents/{doc}:complete-upload", headers=_h(env["sub"], env["t"])).status_code == 202

    assert run_once(postgres_url) == "succeeded"  # the reading job
    assert called == []  # reading did not wait for the AI provider
    assert c.get(f"/v1/documents/{doc}", headers=_h(env["sub"], env["t"])).json()["status"] != "processing"
    db_conn.rollback()
    steps = db_conn.execute("SELECT step, status FROM jobs WHERE subject_id = %s ORDER BY created_at;", (doc,)).fetchall()
    assert steps == [("read_document", "succeeded"), ("ai_fill", "queued")]
    ocr = db_conn.execute(
        "SELECT o.full_text FROM document_ocr o JOIN document_versions dv ON dv.id = o.document_version_id "
        "WHERE dv.document_id = %s;", (doc,)
    ).fetchone()
    assert ocr and "FAC-2026-0412" in ocr[0]

    assert run_once(postgres_url) == "succeeded"  # the AI job
    assert called == [1]
