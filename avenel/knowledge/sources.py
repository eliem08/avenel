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
    max_documents: int | None = None  # founder rule 8 Nov 2026: keep every document, no cap by default
    render: bool = False  # HTML pages rendered in a headless browser (PDFs are always plain HTTP)


SOURCES: tuple[Source, ...] = (
    Source(
        code="sgg_bo",
        label="Secrétariat général du gouvernement — Bulletin officiel",
        seeds=("https://www.sgg.gov.ma/arabe/Accueil.aspx", "https://www.sgg.gov.ma/"),
        follow=(re.compile(r"^https://www\.sgg\.gov\.ma/BO/.+\.pdf$", re.IGNORECASE),),
    ),
    Source(
        code="sgg_bo_fr",
        label="Bulletin officiel — édition de traduction officielle (archive complète, depuis 1912)",
        # The SGG page lists every French BO issue through one same-site JSON call (4,898 issues on
        # 8 Nov 2026, BO n° 1 of 1912 to today). Every issue is kept: all finance laws since the first
        # one are published here. Founder rule 8 Nov 2026: every finance law since the beginning.
        seeds=("https://www.sgg.gov.ma/BulletinOfficiel.aspx",),
        follow=(re.compile(r"^https://www\.sgg\.gov\.ma/BO/(FR|bo_fr)/.+\.pdf$", re.IGNORECASE),),
        render=True,
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
            # every finance-law year page (2010 onwards, amending laws included) ...
            re.compile(r"^https://www\.finances\.gov\.ma/fr/vous-orientez/Pages/(plf|lf-|plfr-)\d{4}\.aspx$", re.IGNORECASE),
            # ... and every PDF they publish (bill body, notes, all annex reports), all years
            re.compile(r"^https://www\.finances\.gov\.ma/Publication/db/\d{4}/[^?#]+\.pdf$", re.IGNORECASE),
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
