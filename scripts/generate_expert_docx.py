"""Generates docs/pilot/AVENEL-travail-expert.docx: what the Moroccan expert must check and sign.

Reads every rule in jurisdiction/ma/*.yaml (including nested ones) whose status is 'needs_expert'
(disabled until signed) or 'source_cited' (enabled, shown "à confirmer"). Values are copied from the pack;
nothing here sets or suggests a tax value.

Usage: python scripts/generate_expert_docx.py   (needs python-docx: pip install python-docx; not an app dependency)
"""

from __future__ import annotations

import datetime
import pathlib
from typing import Any

import yaml
from docx import Document  # type: ignore[import-not-found]
from docx.enum.section import WD_ORIENT  # type: ignore[import-not-found]
from docx.shared import Pt, RGBColor  # type: ignore[import-not-found]

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PACK_DIR = REPO_ROOT / "jurisdiction" / "ma"
OUTPUT_FILE = REPO_ROOT / "docs" / "pilot" / "AVENEL-travail-expert.docx"

TOPICS = {
    "cgnc_seed.yaml": "Plan comptable (CGNC)",
    "compliance.yaml": "Protection des données (CNDP) et conservation",
    "einvoicing.yaml": "Facture électronique",
    "identifiers.yaml": "Identifiants (ICE, IF, RC, RIB, codes banques)",
    "invoice_mentions.yaml": "Mentions obligatoires des factures",
    "issues.yaml": "Anomalies signalées (seuils et libellés)",
    "lettrage.yaml": "Lettrage clients / fournisseurs",
    "oec_position.yaml": "Position de l'Ordre des Experts-Comptables",
    "simpl_tva.yaml": "Télédéclaration TVA (SIMPL)",
    "vat_deduction.yaml": "Déduction de la TVA",
    "vat_filing.yaml": "Déclaration de TVA",
    "vat_rates.yaml": "Taux de TVA",
    "vat_withholding.yaml": "Retenue à la source sur la TVA",
}


def _short(val: Any, limit: int = 160) -> str:
    if val is None:
        return "(aucune valeur : à fournir)"
    text = val if isinstance(val, str) else yaml.safe_dump(val, allow_unicode=True, default_flow_style=True).strip()
    if isinstance(val, list) and len(val) > 3:
        text = f"{len(val)} éléments, dont : " + yaml.safe_dump(val[:3], allow_unicode=True,
                                                                  default_flow_style=True).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _walk(node: Any, path: str, out: list[dict[str, Any]], file: str) -> None:
    if isinstance(node, dict):
        if node.get("status") in ("needs_expert", "source_cited"):
            out.append({"file": file, "key": node.get("key") or path, "status": node["status"],
                        "value": _short(node.get("value")), "source": node.get("source") or "",
                        "note": (node.get("note") or "").strip()})
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _walk(v, f"{node.get('key') or path}.{k}", out, file)
    elif isinstance(node, list):
        for item in node:
            _walk(item, path, out, file)


def collect() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(PACK_DIR.glob("*.yaml")):
        _walk(yaml.safe_load(p.read_text(encoding="utf-8")), p.stem, out, p.name)
    seen, unique = set(), []
    for e in out:
        ident = (e["file"], e["key"], e["status"])
        if ident not in seen:
            seen.add(ident)
            unique.append(e)
    return unique


def _table(doc: Document, rows: list[dict[str, Any]], with_source: bool) -> None:
    headers = ["#", "Règle (clé)", "Valeur actuelle dans AVENEL", "Question / source",
               "Décision (valider / corriger)", "Valeur et référence officielle", "Visa"]
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = h
        for r in t.rows[0].cells[i].paragraphs[0].runs:
            r.bold = True
    for n, e in enumerate(rows, 1):
        c = t.add_row().cells
        c[0].text = str(n)
        c[1].text = e["key"]
        c[2].text = e["value"]
        c[3].text = (f"Source citée : {e['source']}. " if with_source and e["source"] else "") + e["note"]
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8)


def build() -> pathlib.Path:
    entries = collect()
    blocked = [e for e in entries if e["status"] == "needs_expert"]
    confirm = [e for e in entries if e["status"] == "source_cited"]

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    doc.add_heading("AVENEL : travail demandé à l'expert-comptable", 0)
    doc.add_paragraph(f"Généré le {datetime.date.today():%d/%m/%Y} depuis le pack réglementaire "
                      "jurisdiction/ma du dépôt. Les valeurs ci-dessous sont celles du pack ; ce document "
                      "n'en invente aucune.")

    doc.add_heading("Pourquoi ce document", 1)
    doc.add_paragraph(
        "AVENEL n'applique jamais une règle fiscale, comptable ou légale qu'un professionnel marocain "
        "n'a pas validée. Les règles ci-dessous sont soit désactivées (section 2), soit actives mais "
        "affichées « à confirmer » (section 3). Votre visa permet de les activer ou de les corriger.")

    doc.add_heading("Ce que l'expert doit faire", 1)
    for s in [
        (f"Section 2 ({len(blocked)} règles bloquantes) : pour chaque règle, indiquer la valeur correcte et "
        "la référence officielle (article du CGI, loi de finances, circulaire DGI, norme CGNC, BAM, CNDP…). "
        "Ces règles sont désactivées tant qu'elles ne sont pas signées."),
        (f"Section 3 ({len(confirm)} règles à confirmer) : vérifier que la valeur et la source citée sont "
        "exactes et toujours en vigueur pour l'exercice 2026, ou les corriger."),
        ("Section 4 : fixer les paramètres de cabinet (tolérances de lettrage, comptes d'attente, durées "
        "de conservation)."),
        "Signer et dater la section 5. Une règle sans référence officielle reste désactivée.",
    ]:
        doc.add_paragraph(s, style="List Number")

    doc.add_heading(f"2. Règles bloquantes : à fournir ou valider ({len(blocked)})", 1)
    for file in sorted({e["file"] for e in blocked}):
        doc.add_heading(TOPICS.get(file, file), 2)
        _table(doc, [e for e in blocked if e["file"] == file], with_source=False)

    doc.add_heading(f"3. Règles actives « à confirmer » ({len(confirm)})", 1)
    for file in sorted({e["file"] for e in confirm}):
        doc.add_heading(TOPICS.get(file, file), 2)
        _table(doc, [e for e in confirm if e["file"] == file], with_source=True)

    doc.add_heading("4. Paramètres de cabinet à fixer", 1)
    for s in [
        "Tolérance d'écart accepté au lettrage (en MAD), et si l'écart est passé en compte d'écart.",
        "Comptes d'attente par défaut (lignes bancaires non rapprochées, TVA non identifiée).",
        "Durée de conservation légale des pièces justificatives et des relevés bancaires.",
        "Sous-comptes CGNC propres à l'activité de chaque client pilote.",
    ]:
        doc.add_paragraph(s, style="List Bullet")

    doc.add_heading("5. Visa", 1)
    for line in ["Nom et prénom :", "Qualité (expert-comptable inscrit à l'OEC, n° d'inscription) :",
                 "Date :", "Signature et cachet :"]:
        p = doc.add_paragraph(line + " " + "_" * 60)
        p.runs[0].font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT_FILE)
    print(f"{OUTPUT_FILE}: {len(blocked)} blocking, {len(confirm)} to confirm")
    return OUTPUT_FILE


if __name__ == "__main__":
    build()
