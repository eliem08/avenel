"""AI help for fields that rules and OCR missed (B-02), through the residency router.

Order of trust: the deterministic extractor reads first. The AI provider is asked only for fields that are
still empty, and only when the firm's data_residency_policy allows the provider's region (NVIDIA's hosted
API is outside Morocco and the EU, so it needs GLOBAL_ALLOWED). Identifiers (ICE, IF, RIB) are masked
before the text leaves, so the AI never fills them. An amount is kept only if it is printed on the
document (no computed totals, Part A). Every AI value is capped at review confidence and marked
source="ai", so a person checks it. Nothing here sets a tax value.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

import psycopg

from avenel.extraction.router import (
    ProviderCallRequest,
    ProviderRouter,
    sanitize_pii_for_external_call,
)
from avenel.ocr.adapter import OcrResult

AI_REVIEW_CONFIDENCE = 0.6
TEXT_FIELDS = ("invoice_number", "invoice_date", "due_date", "supplier_name", "supplier_address", "client_name")
AMOUNT_FIELDS = ("total_ht", "total_vat", "total_ttc")
NEVER_FROM_AI = ("supplier_ice", "supplier_if", "supplier_rc", "client_ice", "client_if")  # masked before sending

PROMPT = """Tu lis le texte OCR d'une pièce comptable marocaine. Réponds UNIQUEMENT par un objet JSON.
Donne seulement ces champs, avec la valeur exactement comme elle figure sur la pièce, ou null si elle
n'y figure pas : {fields}.
Dates au format AAAA-MM-JJ. Montants en nombre (point décimal). Ne calcule jamais un montant absent de la pièce.

Texte OCR :
<<<
{text}
>>>"""


def ai_configured() -> bool:
    return bool(os.environ.get("NVIDIA_API_KEY")) and os.environ.get("AVENEL_AI_ENABLED", "1") == "1"


def _call_nim(payload: dict[str, Any]) -> dict[str, Any]:
    import httpx

    base = os.environ.get("AVENEL_AI_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    resp = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"},
        json={
            "model": payload["model"],
            "messages": [{"role": "user", "content": payload["prompt"]}],
            "temperature": 0,
            "max_tokens": 800,
        },
        timeout=float(os.environ.get("AVENEL_AI_TIMEOUT_SECONDS", "120")),
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"] or ""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("la réponse du modèle ne contient pas de JSON")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise TypeError("la réponse du modèle n'est pas un objet JSON")
    return parsed


def _amount_on_document(value: float, ocr: OcrResult) -> bool:
    """True if the amount is printed on the page (any common Moroccan/French formatting)."""
    digits = re.sub(r"[^\d]", "", f"{value:.2f}")
    for line in ocr.lines:
        for token in re.findall(r"\d[\d\s.,]*\d", line.text):
            t = re.sub(r"[^\d]", "", token)
            if t == digits or t == digits[:-2]:  # "12000.00" or "12 000"
                return True
    return False


def _date_on_document(iso: str, ocr: OcrResult) -> bool:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso)
    if not m:
        return False
    y, mo, d = m.groups()
    text = re.sub(r"\s", "", ocr.full_text)
    return any(f in text for f in (f"{d}/{mo}/{y}", f"{d}-{mo}-{y}", f"{d}.{mo}.{y}", iso, f"{d}/{mo}/{y[2:]}"))


def _bbox_for(value: str, ocr: OcrResult) -> list[float] | None:
    needle = value.strip().lower()
    for line in ocr.lines:
        if needle and needle in line.text.lower():
            return line.bbox
    return None


def merge_ai_fields(fields: dict[str, Any], ai: dict[str, Any], ocr: OcrResult) -> list[str]:
    """Fills only empty fields from the AI answer. Returns the names filled."""
    filled: list[str] = []
    # Values the rules already gave to a field: the AI may not reuse one for another field
    # (seen on the stack: the invoice date offered again as the due date).
    taken = {str(v.get("value")).strip().lower() for v in fields.values()
             if isinstance(v, dict) and v.get("value") not in (None, "", False, True)}
    for name in TEXT_FIELDS + AMOUNT_FIELDS:
        slot = fields.get(name)
        if not isinstance(slot, dict) or slot.get("value") is not None:
            continue
        raw = ai.get(name)
        if raw is None or raw == "":
            continue
        if name in AMOUNT_FIELDS:
            try:
                value: Any = round(float(str(raw).replace(" ", "").replace(",", ".")), 2)
            except ValueError:
                continue
            if not _amount_on_document(value, ocr):
                continue  # never keep a total the document does not show
            bbox = None
        else:
            value = str(raw).strip()
            if value.lower() in taken:
                continue
            if name in ("invoice_date", "due_date") and not _date_on_document(value, ocr):
                continue  # a date must be well formed and printed on the document
            bbox = _bbox_for(value, ocr)
        slot.update({"value": value, "confidence": AI_REVIEW_CONFIDENCE, "source": "ai", "bbox": bbox or slot.get("bbox")})
        filled.append(name)
    return filled


def _tenant_policy(conn: psycopg.Connection, tenant_id: uuid.UUID) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT data_residency_policy FROM tenants WHERE id = %s;", (tenant_id,))
        row = cur.fetchone()
    return str(row[0]) if row else "MA_ONLY"


def fill_missing_fields(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    ocr: OcrResult,
    fields: dict[str, Any],
    router: ProviderRouter | None = None,
) -> dict[str, Any]:
    """Asks the AI provider for the fields still empty. Returns {"status", "filled", "provider_call_id"}."""
    missing = [n for n in TEXT_FIELDS + AMOUNT_FIELDS if isinstance(fields.get(n), dict) and fields[n].get("value") is None]
    if not missing or not ai_configured() or not ocr.full_text.strip():
        return {"status": "not_needed" if not missing else "not_configured", "filled": [], "provider_call_id": None}

    model = os.environ.get("AVENEL_AI_MODEL", "minimaxai/minimax-m3.1-flash")
    request = ProviderCallRequest(
        provider="nvidia-nim",
        region=os.environ.get("AVENEL_AI_REGION", "us"),
        model=model,
        purpose="extraction_fill",
        payload={"model": model, "prompt": PROMPT.format(
            fields=", ".join(missing), text=sanitize_pii_for_external_call(ocr.full_text)[:12000])},
    )
    p_router = router or ProviderRouter(db_conn=conn)
    try:
        resp = p_router.execute_call(tenant_id, _tenant_policy(conn, tenant_id), request, handler=_call_nim)
    except RuntimeError:
        return {"status": "failed", "filled": [], "provider_call_id": None}  # reading goes on without AI
    if resp.status != "succeeded" or not resp.result:
        return {"status": resp.status, "filled": [], "provider_call_id": resp.provider_call_id}
    filled = merge_ai_fields(fields, resp.result, ocr)
    return {"status": "succeeded", "filled": filled, "provider_call_id": resp.provider_call_id}
