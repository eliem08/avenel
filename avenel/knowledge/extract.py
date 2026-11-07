"""Deterministic reference extraction for the legal knowledge graph.

Finds references only (laws, decrees, dahirs, notes circulaires, Bulletin officiel issues, CGI
articles). It never reads a rate, threshold or deadline out of a text (ARCHITECTURE.md A.2.1).

Arabic BO PDFs are not parsed for references: plain PDF text extraction moves the numbers away
from their words (checked on the real crawl, 7 Nov 2026), so a pattern would record wrong numbers.
The BO issue of such a file is read from its file name (`BO_7556-bis_Ar.pdf`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUM = r"(?:n[°ºo]\.?\s*)"

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("law", re.compile(rf"\bloi\s+(?:organique\s+)?{_NUM}?(\d{{1,3}}[-.]\d{{2}})\b", re.IGNORECASE)),
    ("decree", re.compile(rf"\bd[ée]cret\s+{_NUM}?(2[-.]\d{{2}}[-.]\d{{1,4}})\b", re.IGNORECASE)),
    ("dahir", re.compile(rf"\bdahir\s+{_NUM}?(1[-.]\d{{2}}[-.]\d{{1,4}})\b", re.IGNORECASE)),
    ("circular", re.compile(rf"\bnote\s+circulaire\s+{_NUM}?(\d{{1,4}})\b", re.IGNORECASE)),
    ("bo_issue", re.compile(rf"\b(?:bulletin\s+officiel|B\.?O\.?)\s+{_NUM}?(\d{{4}}(?:[-\s]?bis)?)\b", re.IGNORECASE)),
    ("bo_issue", re.compile(r"\bBO_(\d{4}(?:-bis)?)_(?:Ar|Fr)\.pdf\b", re.IGNORECASE)),
    ("article", re.compile(r"\b(?:CGI|code\s+g[ée]n[ée]ral\s+des\s+imp[ôo]ts)\s*,?\s*art(?:icle|\.)?\s*(\d{1,3})\b", re.IGNORECASE)),
    ("article", re.compile(r"\bart(?:icle|\.)?\s*(\d{1,3})(?:[-\s]?[IVX]+)?\s+du\s+(?:CGI|code\s+g[ée]n[ée]ral\s+des\s+imp[ôo]ts)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Reference:
    kind: str
    key: str
    label: str
    evidence: str


def _normalise(kind: str, raw: str) -> tuple[str, str]:
    raw = re.sub(r"\s+", "", raw).replace(".", "-").replace("مكرر", "-bis")
    raw = re.sub(r"(?i)-?bis$", "-bis", raw)
    labels = {
        "law": f"Loi n° {raw}",
        "decree": f"Décret n° {raw}",
        "dahir": f"Dahir n° {raw}",
        "circular": f"Note circulaire n° {raw}",
        "bo_issue": f"Bulletin officiel n° {raw}",
        "article": f"CGI art. {raw}",
    }
    key = f"CGI art. {raw}" if kind == "article" else raw
    return key, labels[kind]


def _snippet(text: str, start: int, end: int, width: int = 120) -> str:
    a, b = max(0, start - width), min(len(text), end + width)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def extract_references(text: str) -> list[Reference]:
    """Every distinct reference in the text, with the first sentence fragment that shows it."""
    seen: dict[tuple[str, str], Reference] = {}
    for kind, pat in _PATTERNS:
        for m in pat.finditer(text):
            key, label = _normalise(kind, m.group(1))
            if (kind, key) not in seen:
                seen[(kind, key)] = Reference(kind, key, label, _snippet(text, m.start(), m.end()))
    return sorted(seen.values(), key=lambda r: (r.kind, r.key))


def cgi_article_of(source_text: str) -> str | None:
    """`CGI art. 106-II` -> `CGI art. 106`; None when the pack source is not a CGI article."""
    m = re.match(r"^\s*CGI\s+art(?:icle|\.)?\s*(\d{1,3})", source_text, re.IGNORECASE)
    return f"CGI art. {m.group(1)}" if m else None
