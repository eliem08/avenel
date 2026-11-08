"""Polite crawler for the legal knowledge graph, built on Scrapling (docs/plans/phase-7a.md).

Rules fixed here and tested: robots.txt respected (5xx or unreachable = disallowed), allowlisted
URLs only, one request at a time with a minimum delay per host, a 403/429/503 stops the host for the
run. Script-rendered sources use a plain headless Chromium (no stealth, no fingerprint spoofing, no
CAPTCHA solving) with a longer delay; robots.txt and PDFs always go through the plain HTTP fetcher.
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.robotparser
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urldefrag, urlparse

from scrapling.parser import Selector

from avenel.knowledge.sources import Source

USER_AGENT = "AVENEL-KG/0.1 (public legal texts index; contact via eliem08/avenel)"
MIN_DELAY_SECONDS = 5.0
MIN_BROWSER_DELAY_SECONDS = 15.0  # a rendered page loads many resources; be slower
STOP_STATUSES = frozenset({403, 429, 503})
BUSY_STATUSES = frozenset({429, 503})  # the host is busy: pause, slow down, try again
BACKOFF_SECONDS = 600.0  # 10 minutes after a busy answer
MAX_BACKOFFS = 3  # busy this many times in a row: stop the host for the run


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    content_type: str
    body: bytes
    captured: tuple[str, ...] = ()  # same-site data responses seen while rendering (JSON lists)


@dataclass(frozen=True)
class CrawledDocument:
    source_code: str
    url: str
    status: int
    content_type: str
    sha256: str
    title: str | None
    text: str
    original: bytes = b""  # the exact bytes fetched (PDF or rendered HTML), kept forever


Fetch = Callable[[str], Fetched]


def scrapling_fetch(url: str) -> Fetched:  # pragma: no cover - live network, used by the CLI only
    from scrapling.fetchers import Fetcher

    r = Fetcher.get(url, timeout=60, headers={"User-Agent": USER_AGENT}, stealthy_headers=False)
    return Fetched(url, int(r.status), str(r.headers.get("content-type", "")), bytes(r.body))


class BrowserRenderer:  # pragma: no cover - live browser, used by the CLI only
    """Headless Chromium via Playwright; returns the rendered HTML. Use as a context manager."""

    def __init__(self, executable_path: str | None = None) -> None:
        self._exe = executable_path

    def __enter__(self) -> BrowserRenderer:  # noqa: PYI034
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(executable_path=self._exe)
        self._page = self._browser.new_page(user_agent=USER_AGENT)
        return self

    def __exit__(self, *exc: object) -> None:
        self._browser.close()
        self._pw.stop()

    def __call__(self, url: str) -> Fetched:
        # Keep the page's own same-site data calls (e.g. the SGG list of all BO issues is one JSON call):
        # their links are followed like the page's links. Nothing is sent that the page would not send.
        captured: list[str] = []
        host = urlparse(url).netloc

        def on_response(r: Any) -> None:
            if r.request.resource_type in ("xhr", "fetch") and urlparse(r.url).netloc == host:
                try:
                    captured.append(r.text())
                except Exception:  # noqa: BLE001 - a body we cannot read is simply not used
                    return

        self._page.on("response", on_response)
        try:
            res = self._page.goto(url, wait_until="networkidle", timeout=90_000)
        finally:
            self._page.remove_listener("response", on_response)
        status = res.status if res is not None else 0
        return Fetched(url, status, "text/html; rendered", self._page.content().encode("utf-8"), tuple(captured))


def _pdf_text(body: bytes) -> str:
    import pymupdf

    with pymupdf.open(stream=body, filetype="pdf") as doc:
        return "\n".join(str(page.get_text()) for page in doc)


class Crawler:
    def __init__(
        self,
        fetch: Fetch,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        log: Callable[[str], None] = print,
        render: Fetch | None = None,
        known: frozenset[str] = frozenset(),
    ) -> None:
        self._known = known  # files already stored: not requested again (resume)
        self._slow: dict[str, float] = {}  # per-host delay multiplier, doubled after each busy answer
        self._fetch = fetch
        self._render = render
        self._sleep = sleep
        self._clock = clock
        self._log = log
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}
        self.stopped_hosts: set[str] = set()

    def _get(self, url: str, rendered: bool = False, retry_busy: bool = True) -> Fetched | None:
        host = urlparse(url).netloc
        for attempt in range(MAX_BACKOFFS + 1):
            res = self._get_once(url, rendered)
            if res is None or res.status not in BUSY_STATUSES or not retry_busy:
                break
            if attempt == MAX_BACKOFFS:
                break
            self._slow[host] = min(self._slow.get(host, 1.0) * 2, 8.0)
            self._log(f"busy {host}: pause {int(BACKOFF_SECONDS)}s, then delay x{self._slow[host]:g}")
            self._sleep(BACKOFF_SECONDS)
        if res is not None and res.status in STOP_STATUSES:
            self.stopped_hosts.add(host)
        return res

    def _get_once(self, url: str, rendered: bool) -> Fetched | None:
        host = urlparse(url).netloc
        if host in self.stopped_hosts:
            return None
        last = self._last.get(host)
        if last is not None:
            delay = (MIN_BROWSER_DELAY_SECONDS if rendered else MIN_DELAY_SECONDS) * self._slow.get(host, 1.0)
            wait = delay - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        fetch = self._render if rendered and self._render is not None else self._fetch
        try:
            res = fetch(url)
        except Exception as exc:  # noqa: BLE001 - network failure: stop the host, keep the run going
            self._log(f"GET {url} -> error {type(exc).__name__}")
            self.stopped_hosts.add(host)
            return None
        finally:
            self._last[host] = self._clock()
        self._log(f"{'RENDER' if fetch is self._render else 'GET'} {url} -> {res.status}")
        return res

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        host = parts.netloc
        if host not in self._robots:
            res = self._get(f"{parts.scheme}://{host}/robots.txt", retry_busy=False)
            if res is None or res.status >= 500:
                self._robots[host] = None  # unknown policy: disallow everything
            else:
                rp = urllib.robotparser.RobotFileParser()
                if res.status >= 400:
                    rp.parse([])  # no robots.txt: allowed
                else:
                    rp.parse(res.body.decode("utf-8", "replace").splitlines())
                self._robots[host] = rp
        policy = self._robots[host]
        return policy is not None and policy.can_fetch(USER_AGENT, url)

    def crawl(self, source: Source) -> Iterator[CrawledDocument]:
        if not source.enabled:
            self._log(f"skip {source.code}: {source.disabled_reason}")
            return
        if source.render and self._render is None:
            self._log(f"skip {source.code}: needs browser rendering (run with --render)")
            return
        queue = list(source.seeds)
        seen: set[str] = set()
        produced = 0
        while queue and (source.max_documents is None or produced < source.max_documents):
            url = urldefrag(queue.pop(0))[0]
            if url in seen:
                continue
            seen.add(url)
            if url in self._known and url.lower().endswith(".pdf"):
                continue  # already stored with its original; a listing page is always re-read
            if not self.allowed(url):
                self._log(f"robots disallow {url}")
                continue
            res = self._get(url, rendered=source.render and not url.lower().endswith(".pdf"))
            if res is None or res.status != 200:
                continue
            title: str | None
            if "pdf" in res.content_type or url.lower().endswith(".pdf"):
                text, title = _pdf_text(res.body), str(url.rsplit("/", 1)[-1])
            else:
                page = Selector(content=res.body, url=url)
                found = page.css("title::text").get()
                title = str(found) if found is not None else None
                for link in _links(page, res.body, res.captured):
                    if any(p.match(link) for p in source.follow) and link not in seen:
                        queue.append(link)
                text = re.sub(r"\s+", " ", " ".join(page.css("body *::text").getall())).strip()
            # Every fetched page and file is kept, seeds included (founder rule 8 Nov 2026: forget nothing).
            text = text.replace("\x00", "")  # PostgreSQL text cannot hold NUL; some BO PDFs contain it
            produced += 1
            yield CrawledDocument(
                source.code, url, res.status, res.content_type or "application/octet-stream",
                hashlib.sha256(res.body).hexdigest(), (title or "").strip() or None, text, res.body,
            )


def _links(page: Selector, body: bytes, captured: tuple[str, ...] = ()) -> list[str]:
    hrefs = [page.urljoin(a.attrib.get("href", "")) for a in page.css("a[href]")]
    hrefs += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace"))  # sitemaps
    for data in captured:  # file paths inside JSON data responses, e.g. "BoUrl": "/BO/FR/.../BO_7554_Fr.pdf"
        plain = data.replace('\\"', '"').replace("\\/", "/")  # JSON may be encoded twice
        hrefs += [page.urljoin(m) for m in re.findall(r'"((?:https?:)?[^"\s]*?\.pdf)"', plain, re.IGNORECASE)]
    return [h.replace(":443/", "/") for h in hrefs if h.startswith("https://")]
