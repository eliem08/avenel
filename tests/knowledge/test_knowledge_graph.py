"""Phase 7a legal knowledge graph: crawler politeness, reference extraction, storage, pack links.

All fetches are fixtures (A.2.7); no network.
"""

from __future__ import annotations

import dataclasses
import re
import uuid

import psycopg
import pymupdf
import pytest

from avenel.jurisdiction.loader import JurisdictionPackLoader
from avenel.knowledge.crawler import (
    MIN_BROWSER_DELAY_SECONDS,
    MIN_DELAY_SECONDS,
    CrawledDocument,
    Crawler,
    Fetched,
)
from avenel.knowledge.extract import cgi_article_of, extract_references
from avenel.knowledge.graph import evidence_for_rule, link_pack, store_document
from avenel.knowledge.sources import Source, source_by_code

HOST = "https://www.example.gov.ma"


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return bytes(data)


class FakeWeb:
    def __init__(self, pages: dict[str, Fetched]) -> None:
        self.pages = pages
        self.requests: list[str] = []

    def __call__(self, url: str) -> Fetched:
        self.requests.append(url)
        return self.pages.get(url, Fetched(url, 404, "text/html", b""))


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.now += s


def _html(url: str, body: str) -> Fetched:
    return Fetched(url, 200, "text/html; charset=utf-8", f"<html><title>T</title><body>{body}</body></html>".encode())


SOURCE = Source(
    code="test_src",
    label="Test",
    seeds=(f"{HOST}/",),
    follow=(re.compile(rf"^{re.escape(HOST)}/BO/.+\.pdf$"),),
)


def _crawler(web: FakeWeb) -> tuple[Crawler, FakeClock, list[str]]:
    clock, log = FakeClock(), []
    return Crawler(web, sleep=clock.sleep, clock=clock.clock, log=log.append), clock, log


# ---------- crawler ----------

def test_follows_only_allowlisted_links_and_reads_pdf_text():
    web = FakeWeb({
        f"{HOST}/robots.txt": Fetched("", 404, "text/html", b""),
        f"{HOST}/": _html(f"{HOST}/", '<a href="/BO/2026/BO_7556_Fr.pdf">BO</a><a href="/other.pdf">x</a>'
                          '<a href="https://evil.example.com/BO/x.pdf">e</a>'),
        f"{HOST}/BO/2026/BO_7556_Fr.pdf": Fetched("", 200, "application/pdf",
                                                  _pdf("Loi n 9-88 et CGI art. 106 du present texte")),
    })
    crawler, _, _ = _crawler(web)
    docs = list(crawler.crawl(SOURCE))
    assert [d.url for d in docs] == [f"{HOST}/BO/2026/BO_7556_Fr.pdf"]
    assert "CGI art. 106" in docs[0].text
    assert not any("other.pdf" in u or "evil" in u for u in web.requests)


def test_nul_bytes_in_extracted_text_are_removed(monkeypatch: pytest.MonkeyPatch):
    # Found in the real crawl (7 Nov 2026): a Bulletin officiel PDF yields text with NUL bytes.
    import avenel.knowledge.crawler as crawler_mod

    monkeypatch.setattr(crawler_mod, "_pdf_text", lambda body: "BO\x00 7556")
    web = FakeWeb({
        f"{HOST}/robots.txt": Fetched("", 404, "text/html", b""),
        f"{HOST}/": _html(f"{HOST}/", '<a href="/BO/a.pdf">a</a>'),
        f"{HOST}/BO/a.pdf": Fetched("", 200, "application/pdf", b"%PDF"),
    })
    crawler, _, _ = _crawler(web)
    assert [d.text for d in crawler.crawl(SOURCE)] == ["BO 7556"]


def test_robots_disallow_is_respected():
    web = FakeWeb({
        f"{HOST}/robots.txt": Fetched("", 200, "text/plain", b"User-agent: *\nDisallow: /BO/\n"),
        f"{HOST}/": _html(f"{HOST}/", '<a href="/BO/a.pdf">a</a>'),
    })
    crawler, _, log = _crawler(web)
    assert list(crawler.crawl(SOURCE)) == []
    assert f"{HOST}/BO/a.pdf" not in web.requests
    assert any(line.startswith("robots disallow") for line in log)


@pytest.mark.parametrize("status", [500, 503])
def test_robots_5xx_disallows_the_whole_host(status: int):
    web = FakeWeb({f"{HOST}/robots.txt": Fetched("", status, "text/html", b"")})
    crawler, _, _ = _crawler(web)
    assert list(crawler.crawl(SOURCE)) == []
    assert web.requests == [f"{HOST}/robots.txt"]


def test_503_stops_the_host_for_the_run():
    web = FakeWeb({
        f"{HOST}/robots.txt": Fetched("", 404, "text/html", b""),
        f"{HOST}/": _html(f"{HOST}/", '<a href="/BO/a.pdf">a</a><a href="/BO/b.pdf">b</a>'),
        f"{HOST}/BO/a.pdf": Fetched("", 503, "text/html", b""),
        f"{HOST}/BO/b.pdf": Fetched("", 200, "application/pdf", _pdf("x")),
    })
    crawler, _, _ = _crawler(web)
    assert list(crawler.crawl(SOURCE)) == []
    assert f"{HOST}/BO/b.pdf" not in web.requests


def test_minimum_delay_between_requests_to_one_host():
    web = FakeWeb({
        f"{HOST}/robots.txt": Fetched("", 404, "text/html", b""),
        f"{HOST}/": _html(f"{HOST}/", '<a href="/BO/a.pdf">a</a>'),
        f"{HOST}/BO/a.pdf": Fetched("", 200, "application/pdf", _pdf("x")),
    })
    crawler, clock, _ = _crawler(web)
    list(crawler.crawl(SOURCE))
    assert len(web.requests) == 3
    assert clock.slept == [MIN_DELAY_SECONDS, MIN_DELAY_SECONDS]


def test_disabled_sources_make_no_request():
    web = FakeWeb({})
    crawler, _, _ = _crawler(web)
    assert list(crawler.crawl(source_by_code("marches_publics"))) == []
    assert web.requests == []


def test_render_source_is_skipped_without_a_browser():
    web = FakeWeb({})
    crawler, _, log = _crawler(web)
    assert list(crawler.crawl(source_by_code("finances"))) == []
    assert web.requests == []
    assert any("needs browser rendering" in line for line in log)


def test_dgi_with_browser_is_still_blocked_by_its_503_robots():
    # 8 Nov 2026: tax.gov.ma/robots.txt answers 503. RFC 9309: unreachable robots = disallow all.
    web, renders = FakeWeb({"https://www.tax.gov.ma/robots.txt": Fetched("", 503, "text/html", b"")}), []
    clock = FakeClock()
    crawler = Crawler(web, sleep=clock.sleep, clock=clock.clock, log=lambda _: None,
                      render=lambda u: renders.append(u) or Fetched(u, 200, "text/html", b""))
    assert list(crawler.crawl(source_by_code("dgi"))) == []
    assert web.requests == ["https://www.tax.gov.ma/robots.txt"]
    assert renders == []


def test_render_pages_in_browser_and_pdfs_over_plain_http():
    seed = f"{HOST}/fr/lf.aspx"
    pdf = f"{HOST}/Publication/db/2026/corps-LF2026-fr.pdf"
    web = FakeWeb({
        f"{HOST}/robots.txt": Fetched("", 404, "text/html", b""),
        pdf: Fetched(pdf, 200, "application/pdf", _pdf("Article 6 du CGI, voir CGI art. 106")),
    })
    rendered: list[str] = []

    def render(url: str) -> Fetched:
        rendered.append(url)
        return _html(url, f'<a href="{pdf}">Corps</a><a href="/Publication/db/2026/autre.pdf">x</a>')

    clock = FakeClock()
    crawler = Crawler(web, sleep=clock.sleep, clock=clock.clock, log=lambda _: None, render=render)
    src = Source(code="test_src", label="T", seeds=(seed,), render=True,
                 follow=(re.compile(rf"^{re.escape(HOST)}/Publication/db/20\d\d/corps-[A-Za-z0-9-]*\.pdf$"),))
    docs = list(crawler.crawl(src))
    assert rendered == [seed]
    assert web.requests == [f"{HOST}/robots.txt", pdf]
    assert [d.url for d in docs] == [pdf]
    assert {r.key for r in extract_references(docs[0].text)} == {"CGI art. 6", "CGI art. 106"}


def test_browser_pages_wait_longer_between_requests():
    seeds = (f"{HOST}/a.aspx", f"{HOST}/b.aspx")
    web = FakeWeb({f"{HOST}/robots.txt": Fetched("", 404, "text/html", b"")})
    clock = FakeClock()
    crawler = Crawler(web, sleep=clock.sleep, clock=clock.clock, log=lambda _: None,
                      render=lambda u: _html(u, ""))
    list(crawler.crawl(Source(code="test_src", label="T", seeds=seeds, follow=(), render=True)))
    assert clock.slept == [MIN_BROWSER_DELAY_SECONDS, MIN_BROWSER_DELAY_SECONDS]


def test_finances_patterns_keep_only_finance_law_texts():
    follow = source_by_code("finances").follow
    base = "https://www.finances.gov.ma/Publication/db/2027/"
    keep = ["corps-PLF2027-fr.pdf", "Note-presentation_Fr.pdf", "Rapport-depenses-fiscales_Fr.pdf"]
    drop = ["Rapport-Dette-publique_Fr.pdf", "Rapport-Genre_Fr.pdf", "Rapport-SEGMA_Fr.pdf"]
    assert all(any(p.match(base + f) for p in follow) for f in keep)
    assert not any(any(p.match(base + f) for p in follow) for f in drop)


def test_max_documents_cap():
    links = "".join(f'<a href="/BO/{i}.pdf">{i}</a>' for i in range(5))
    pages = {f"{HOST}/robots.txt": Fetched("", 404, "text/html", b""), f"{HOST}/": _html(f"{HOST}/", links)}
    pages |= {f"{HOST}/BO/{i}.pdf": Fetched("", 200, "application/pdf", _pdf(str(i))) for i in range(5)}
    crawler, _, _ = _crawler(FakeWeb(pages))
    assert len(list(crawler.crawl(dataclasses.replace(SOURCE, max_documents=2)))) == 2


# ---------- extraction ----------

def test_reference_extraction_golden():
    text = (
        "Conformément à la loi n° 9-88 relative aux obligations comptables, au décret n° 2-06-574, "
        "au dahir n° 1-92-138, à la note circulaire n° 736 et au Bulletin officiel n° 7556-bis, "
        "voir l'article 106-II du CGI et CGI art. 117."
    )
    got = {(r.kind, r.key) for r in extract_references(text)}
    assert got == {
        ("law", "9-88"), ("decree", "2-06-574"), ("dahir", "1-92-138"), ("circular", "736"),
        ("bo_issue", "7556-bis"), ("article", "CGI art. 106"), ("article", "CGI art. 117"),
    }


def test_extraction_never_returns_values():
    refs = extract_references("Le taux de 20 % et le plafond de 5 000 dirhams par jour.")
    assert refs == []


def test_bo_issue_read_from_the_file_name_when_text_is_arabic(db_conn: psycopg.Connection):
    url = f"{HOST}/BO/AR/{uuid.uuid4()}/BO_7556-bis_Ar.pdf"
    store_document(db_conn, _doc("الجريدة الرسمية عدد\n1985 ماي08", url=url, sha="c" * 64))
    with db_conn.cursor() as cur:
        cur.execute(
            """SELECT n.kind, n.key FROM kg_edges e JOIN kg_nodes n ON n.id = e.to_node
                JOIN kg_documents d ON d.id = e.document_id WHERE d.url = %s AND e.kind = 'mentions'""",
            (url,),
        )
        assert cur.fetchall() == [("bo_issue", "7556-bis")]


def test_cgi_article_of_pack_source():
    assert cgi_article_of("CGI art. 106-II") == "CGI art. 106"
    assert cgi_article_of("Loi 9-88 art. 22") is None


# ---------- storage (database) ----------

def _doc(text: str, url: str = f"{HOST}/BO/x.pdf", sha: str = "a" * 64) -> CrawledDocument:
    return CrawledDocument("sgg_bo", url, 200, "application/pdf", sha, "x.pdf", text)


def test_store_dedups_by_hash_and_versions_on_change(db_conn: psycopg.Connection):
    a, new_a = store_document(db_conn, _doc("CGI art. 106"))
    b, new_b = store_document(db_conn, _doc("CGI art. 106"))
    c, new_c = store_document(db_conn, _doc("CGI art. 106 modifié", sha="b" * 64))
    assert (new_a, new_b, new_c) == (True, False, True)
    assert a == b != c


def test_documents_are_append_only(db_conn: psycopg.Connection):
    doc_id, _ = store_document(db_conn, _doc("x"))
    with pytest.raises(psycopg.Error), db_conn.cursor() as cur:
        cur.execute("UPDATE kg_documents SET title = 'y' WHERE id = %s", (doc_id,))


def test_pack_rule_links_to_crawled_evidence(db_conn: psycopg.Connection):
    pack = JurisdictionPackLoader()
    assert link_pack(db_conn, pack) >= 1
    store_document(db_conn, _doc("Le paiement en espèces visé à l'article 106-II du CGI ...", url=f"{HOST}/BO/{uuid.uuid4()}.pdf"))
    ev = evidence_for_rule(db_conn, "vat.deduction.cash_limit.basis")
    assert ev and ev[0]["key"] == "CGI art. 106"
    assert "article 106-II du CGI" in ev[0]["evidence"]


def test_pack_values_are_untouched_by_the_graph(db_conn: psycopg.Connection):
    before = JurisdictionPackLoader().rules
    link_pack(db_conn, JurisdictionPackLoader())
    store_document(db_conn, _doc("CGI art. 106: plafond porté à 1 dirham"))
    assert JurisdictionPackLoader().rules == before


def test_app_role_can_insert_but_never_change_or_delete(app_conn: psycopg.Connection):
    doc_id, _ = store_document(app_conn, _doc("CGI art. 117", url=f"{HOST}/BO/{uuid.uuid4()}.pdf"))
    for stmt in ("UPDATE kg_nodes SET label = 'x'", "DELETE FROM kg_edges", "UPDATE kg_documents SET title = 'x'"):
        with app_conn.cursor() as cur:
            cur.execute("SAVEPOINT s")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(stmt)
            cur.execute("ROLLBACK TO SAVEPOINT s")
    assert doc_id
