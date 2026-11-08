"""Allowlisted public sources for the legal knowledge graph (docs/plans/phase-7a.md).

Only these hosts and path patterns are fetched. Script-rendered sites (finances, DGI) use a slow
headless browser, still behind robots.txt. Marchés publics is disabled: the TGR portal is suspended.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    code: str
    label: str
    seeds: tuple[str, ...]
    follow: tuple[re.Pattern[str], ...]
    enabled: bool = True
    disabled_reason: str | None = None
    max_documents: int = 50
    render: bool = False  # HTML pages rendered in a headless browser (PDFs are always plain HTTP)


SOURCES: tuple[Source, ...] = (
    Source(
        code="sgg_bo",
        label="Secrétariat général du gouvernement — Bulletin officiel",
        seeds=("https://www.sgg.gov.ma/arabe/Accueil.aspx", "https://www.sgg.gov.ma/"),
        follow=(re.compile(r"^https://www\.sgg\.gov\.ma/BO/.+\.pdf$", re.IGNORECASE),),
    ),
    Source(
        code="finances",
        label="Ministère de l'économie et des finances — lois de finances",
        # Pages are rendered by script (SharePoint); founder decision 8 Nov 2026: slow browser rendering.
        # LF 2026 is the law in force; PLF 2027 is a bill, labelled as such by its file name.
        seeds=(
            "https://www.finances.gov.ma/fr/vous-orientez/Pages/plf2026.aspx",
            "https://www.finances.gov.ma/fr/vous-orientez/Pages/plf2027.aspx",
        ),
        follow=(
            re.compile(
                r"^https://www\.finances\.gov\.ma/Publication/db/20\d\d/"
                r"(corps-[A-Za-z0-9-]*|Note-presentation[A-Za-z_-]*|Rapport-depenses-fiscales[A-Za-z_-]*)\.pdf$",
                re.IGNORECASE,
            ),
        ),
        render=True,
    ),
    Source(
        code="dgi",
        label="Direction générale des impôts",
        seeds=("https://www.tax.gov.ma/wps/portal/DGI",),
        follow=(),
        render=True,
        # Browser rendering is allowed (8 Nov 2026) but robots.txt answers 503, which RFC 9309 treats as
        # "disallow everything". Enabled so the robots check runs each time; nothing is fetched until it answers.
    ),
    Source(
        code="marches_publics",
        label="Portail des marchés publics (TGR)",
        seeds=("https://www.marchespublics.gov.ma/",),
        follow=(),
        enabled=False,
        disabled_reason="portal suspended by the TGR for security reasons (7 Nov 2026)",
    ),
)


def source_by_code(code: str) -> Source:
    for s in SOURCES:
        if s.code == code:
            return s
    raise KeyError(code)
