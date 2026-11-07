"""Allowlisted public sources for the legal knowledge graph (docs/plans/phase-7a.md).

Only these hosts and path patterns are fetched. DGI, finances and marchés publics are listed but
disabled: the DGI robots.txt answers 5xx and its pages need script rendering; the finances sitemap
is empty and its menus are script-rendered; the TGR procurement portal is suspended. Re-enable only after a human decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    code: str
    label: str
    seeds: tuple[str, ...]
    follow: tuple[re.Pattern[str], ...]
    enabled: bool = True
    disabled_reason: str | None = None
    max_documents: int = 50
    extra_hosts: tuple[str, ...] = field(default_factory=tuple)


SOURCES: tuple[Source, ...] = (
    Source(
        code="sgg_bo",
        label="Secrétariat général du gouvernement — Bulletin officiel",
        seeds=("https://www.sgg.gov.ma/arabe/Accueil.aspx", "https://www.sgg.gov.ma/"),
        follow=(re.compile(r"^https://www\.sgg\.gov\.ma/BO/.+\.pdf$", re.IGNORECASE),),
    ),
    Source(
        code="finances",
        label="Ministère de l'économie et des finances (normalisation comptable, lois de finances)",
        seeds=("https://www.finances.gov.ma/sitemap0.xml",),
        follow=(
            re.compile(r"^https://www\.finances\.gov\.ma(:443)?/fr/.*(normalisation|comptab|loi-de-finances|loi_de_finances|CNC).*", re.IGNORECASE),
            re.compile(r"^https://www\.finances\.gov\.ma(:443)?/.*\.pdf$", re.IGNORECASE),
        ),
        enabled=False,
        disabled_reason="sitemap0.xml is empty and menus are rendered by script; awaiting decision",
    ),
    Source(
        code="dgi",
        label="Direction générale des impôts",
        seeds=("https://www.tax.gov.ma/wps/portal/DGI",),
        follow=(),
        enabled=False,
        disabled_reason="robots.txt answers 5xx and pages need script rendering; awaiting decision",
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
