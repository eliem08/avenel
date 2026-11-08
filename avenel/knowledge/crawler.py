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
from urllib.parse import urldefrag, urlparse

from scrapling.parser import Selector

from avenel.knowledge.sources import Source

USER_AGENT = "AVENEL-KG/0.1 (public legal texts index; contact via eliem08/avenel)"
MIN_DELAY_SECONDS = 5.0
MIN_BROWSER_DELAY_SECONDS = 15.0  # a rendered page loads many resources; be slower
STOP_STATUSES = frozenset({403, 429, 503})


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class CrawledDocument:
    source_code: str
    url: str
    status: int
    content_type: str
    sha256: str
    title: str | None
    text: str


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
        res = self._page.goto(url, wait_until="networkidle", timeout=90_000)
        status = res.status if res is not None else 0
        return Fetched(url, status, "text/html; rendered", self._page.content().encode("utf-8"))


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
    ) -> None:
        self._fetch = fetch
        self._render = render
        self._sleep = sleep
        self._clock = clock
        self._log = log
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}
        self.stopped_hosts: set[str] = set()

    def _get(self, url: str, rendered: bool = False) -> Fetched | None:
        host = urlparse(url).netloc
        if host in self.stopped_hosts:
            return None
        last = self._last.get(host)
        if last is not None:
            delay = MIN_BROWSER_DELAY_SECONDS if rendered else MIN_DELAY_SECONDS
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
        if res.status in STOP_STATUSES:
            self.stopped_hosts.add(host)
        return res

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        host = parts.netloc
        if host not in self._robots:
            res = self._get(f"{parts.scheme}://{host}/robots.txt")
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
        while queue and produced < source.max_documents:
            url = urldefrag(queue.pop(0))[0]
            if url in seen:
                continue
            seen.add(url)
            if not self.allowed(url):
                self._log(f"robots disallow {url}")
                continue
            res = self._get(url, rendered=source.render and not url.lower().endswith(".pdf"))
            if res is None or res.status != 200:
                continue
            is_seed = url in source.seeds
            title: str | None
            if "pdf" in res.content_type or url.lower().endswith(".pdf"):
                text, title = _pdf_text(res.body), str(url.rsplit("/", 1)[-1])
            else:
                page = Selector(content=res.body, url=url)
                found = page.css("title::text").get()
                title = str(found) if found is not None else None
                for link in _links(page, res.body):
                    if any(p.match(link) for p in source.follow) and link not in seen:
                        queue.append(link)
                text = re.sub(r"\s+", " ", " ".join(page.css("body *::text").getall())).strip()
            if is_seed and not any(p.match(url) for p in source.follow):
                continue  # seeds are for discovery; only allowlisted pages become documents
            text = text.replace("\x00", "")  # PostgreSQL text cannot hold NUL; some BO PDFs contain it
            produced += 1
            yield CrawledDocument(
                source.code, url, res.status, res.content_type or "application/octet-stream",
                hashlib.sha256(res.body).hexdigest(), (title or "").strip() or None, text,
            )


def _links(page: Selector, body: bytes) -> list[str]:
    hrefs = [page.urljoin(a.attrib.get("href", "")) for a in page.css("a[href]")]
    hrefs += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace"))  # sitemaps
    return [h.replace(":443/", "/") for h in hrefs if h.startswith("https://")]
