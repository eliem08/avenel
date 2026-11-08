"""Operations command: crawl the allowlisted public sources and update the legal knowledge graph.

Usage: python scripts/kg_crawl.py [--source sgg_bo] [--max 10]
Runs as the application role (AVENEL_KG_DATABASE_URL, default avenel_app on localhost). Prints one line per HTTP request.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg

from avenel.jurisdiction.loader import JurisdictionPackLoader
from avenel.knowledge.crawler import BrowserRenderer, Crawler, scrapling_fetch
from avenel.knowledge.graph import link_pack, rebuild_mentions, store_all
from avenel.knowledge.sources import SOURCES


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="append", help="source code (repeatable); default: all enabled")
    ap.add_argument("--max", type=int, default=None, help="cap documents per source")
    ap.add_argument("--render", action="store_true", help="enable the headless browser for script-rendered sources")
    ap.add_argument("--chromium", default=None, help="Chromium executable (default: Playwright's own)")
    args = ap.parse_args()
    url = os.environ.get("AVENEL_KG_DATABASE_URL", "postgresql://avenel_app@localhost:5432/avenel")
    with contextlib.ExitStack() as stack:
        render = stack.enter_context(BrowserRenderer(args.chromium)) if args.render else None
        with psycopg.connect(url) as conn:  # resume: files already stored are not requested again
            known = frozenset(row[0] for row in conn.execute("SELECT DISTINCT url FROM kg_documents"))
        return _run(args, url, Crawler(scrapling_fetch, render=render, known=known))


def _run(args: argparse.Namespace, url: str, crawler: Crawler) -> int:
    with psycopg.connect(url) as conn:
        print(f"pack rules linked: {link_pack(conn, JurisdictionPackLoader())}")
        print(f"stored documents re-read: {rebuild_mentions(conn)}")
        conn.commit()
        for src in SOURCES:
            if args.source and src.code not in args.source:
                continue
            if args.max is not None:
                src = dataclasses.replace(src, max_documents=args.max)
            created, skipped = store_all(conn, crawler.crawl(src))
            print(f"{src.code}: {created} new documents, {skipped} unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
