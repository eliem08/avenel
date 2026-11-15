"""AI help for missing fields (B-02): fills only empty fields, never identifiers or unprinted amounts,
always at review confidence, and never leaves Morocco unless the firm's policy allows it. No network here."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from avenel.extraction import ai_fill
from avenel.extraction.router import ProviderCallResponse
from avenel.ocr.adapter import OcrLine, OcrResult
from tests.helpers import seed_tenant


def _ocr(*lines: str) -> OcrResult:
    ocr_lines = [OcrLine(text=t, confidence=0.9, page=1, bbox=[0.1, 0.1 * i, 0.5, 0.1 * i + 0.05], words=[])
                 for i, t in enumerate(lines, 1)]
    return OcrResult(full_text="\n".join(lines), page_count=1, lines=ocr_lines, words=[])


def _empty(*names: str) -> dict:
    return {n: {"value": None, "confidence": 0.0, "page": 1, "bbox": None} for n in names}


OCR = _ocr("SOCIETE ALPHA SARL", "Facture N° FA-77", "ICE 001500000000099", "Total TTC : 12 000,00 MAD")


def test_fills_only_empty_fields_at_review_confidence():
    fields = _empty("supplier_name", "invoice_number")
    fields["invoice_number"] = {"value": "FA-77", "confidence": 0.97, "page": 1, "bbox": None}
    filled = ai_fill.merge_ai_fields(fields, {"supplier_name": "SOCIETE ALPHA SARL", "invoice_number": "AUTRE"}, OCR)
    assert filled == ["supplier_name"]
    assert fields["invoice_number"]["value"] == "FA-77"  # a value read by the rules is never replaced
    assert fields["supplier_name"] == {"value": "SOCIETE ALPHA SARL", "confidence": ai_fill.AI_REVIEW_CONFIDENCE,
                                       "page": 1, "bbox": OCR.lines[0].bbox, "source": "ai"}


def test_an_amount_not_printed_on_the_document_is_dropped():
    fields = _empty("total_ttc", "total_ht")
    filled = ai_fill.merge_ai_fields(fields, {"total_ttc": "12000.00", "total_ht": 10000}, OCR)
    assert filled == ["total_ttc"]  # 12 000,00 is printed; 10 000 is not (it would be a computed total)
    assert fields["total_ht"]["value"] is None


def test_identifiers_and_badly_formed_dates_are_never_taken_from_the_ai():
    fields = _empty("invoice_date", "supplier_ice")
    filled = ai_fill.merge_ai_fields(fields, {"invoice_date": "12/09/2026", "supplier_ice": "001500000000099"}, OCR)
    assert filled == []
    assert fields["supplier_ice"]["value"] is None


def test_no_key_means_no_call(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    out = ai_fill.fill_missing_fields(None, uuid.uuid4(), OCR, _empty("supplier_name"))  # type: ignore[arg-type]
    assert out["status"] == "not_configured"


def test_ma_only_firm_is_refused_and_recorded(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-not-a-key")
    t_id = seed_tenant(db_conn, "Cabinet MA Only")  # default policy MA_ONLY
    fields = _empty("supplier_name")
    out = ai_fill.fill_missing_fields(db_conn, t_id, OCR, fields)
    assert out["status"] == "refused_by_policy"
    assert fields["supplier_name"]["value"] is None
    with db_conn.cursor() as cur:
        cur.execute("SELECT provider, status FROM provider_calls WHERE id = %s;", (out["provider_call_id"],))
        assert cur.fetchone() == ("nvidia-nim", "refused_by_policy")


def test_identifiers_are_masked_before_leaving(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-not-a-key")
    sent: dict = {}

    class FakeRouter:
        def execute_call(self, tenant_id, policy, request, handler=None):
            sent.update(request.payload)
            return ProviderCallResponse(uuid.uuid4(), "succeeded", {"supplier_name": "SOCIETE ALPHA SARL"}, {}, 0.0)

    monkeypatch.setattr(ai_fill, "_tenant_policy", lambda conn, t: "GLOBAL_ALLOWED")
    fields = _empty("supplier_name")
    out = ai_fill.fill_missing_fields(None, uuid.uuid4(), OCR, fields, router=FakeRouter())  # type: ignore[arg-type]
    assert out["filled"] == ["supplier_name"]
    assert "001500000000099" not in sent["prompt"]


def test_a_date_not_printed_or_already_used_is_dropped():
    ocr = _ocr("Facture N° FA-77", "Date : 12/09/2026", "Echeance : 12/10/2026")
    fields = _empty("due_date")
    fields["invoice_date"] = {"value": "2026-09-12", "confidence": 0.97, "page": 1, "bbox": None}
    assert ai_fill.merge_ai_fields(fields, {"due_date": "2026-09-12"}, ocr) == []  # already the invoice date
    assert ai_fill.merge_ai_fields(fields, {"due_date": "2026-11-30"}, ocr) == []  # not on the document
    assert ai_fill.merge_ai_fields(fields, {"due_date": "2026-10-12"}, ocr) == ["due_date"]
