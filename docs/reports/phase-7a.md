# Phase 7a report — legal knowledge graph prototype (Scrapling)

Date: 7 Nov 2026. Plan: `docs/plans/phase-7a.md`. Status: prototype, stopped for review.
ARCHITECTURE.md is **not** changed yet (D.9 and the Part G entry wait for your approval).

## Built

- `db/migrations/012_knowledge_graph` — `kg_documents` (append-only, trigger), `kg_nodes`, `kg_edges`.
  Global public data, no `tenant_id`. `avenel_app`: SELECT and INSERT only.
- `avenel/knowledge/sources.py` — allowlist of 4 sources with seeds and URL patterns; 3 disabled with a reason.
- `avenel/knowledge/crawler.py` — Scrapling `Fetcher` (plain HTTP) and Scrapling `Selector` for links;
  robots.txt respected (5xx = disallowed), 5 s between requests per host, 403/429/503 stops the host,
  PDF text with PyMuPDF, SHA-256 per fetch, document cap per source. No stealth browser.
- `avenel/knowledge/extract.py` — deterministic references only (loi, décret, dahir, note circulaire,
  BO number, CGI article). No values.
- `avenel/knowledge/graph.py` — storage with dedup by hash, `published_by` / `mentions` / `cites_source`
  edges, `link_pack` (22 pack rules whose `source:` cites a CGI article), `evidence_for_rule`,
  `rebuild_mentions`.
- `scripts/kg_crawl.py` — operations command, runs as `avenel_app`.

## Tested (fixtures, no network)

`tests/knowledge/test_knowledge_graph.py`, 18 tests: allowlist, robots allow/deny/5xx, host stop on 503,
delay, disabled sources make no request, cap, NUL removal, reference golden cases, no values extracted,
BO number from file name, dedup and versioning, append-only, pack rule → crawled evidence, pack values
untouched, app role cannot UPDATE/DELETE. Migration test updated to 12. The privileges guard
(`tests/rls/test_app_role_privileges_match_code.py`) caught that the writer lives in `avenel/` and needed
app-role grants; fixed with INSERT-only grants, not by moving the code.

## Real crawl (docker Postgres, `--max 5`), request log

```
pack rules linked: 22
stored documents re-read: 4
GET https://www.sgg.gov.ma/robots.txt -> 404
GET https://www.sgg.gov.ma/arabe/Accueil.aspx -> 200
GET https://www.sgg.gov.ma/ -> 200
GET https://www.sgg.gov.ma/BO/AR/3111/2026/BO_7556-bis_Ar.pdf -> 200
GET https://www.sgg.gov.ma/BO/AR/3111/2025/ECI_21_Ar.pdf -> 200
GET https://www.sgg.gov.ma/BO/AR/3111/2026/BOACF_1450.pdf -> 200
GET https://www.sgg.gov.ma/BO/AR/3111/2026/BOAL_5946.pdf -> 200
sgg_bo: 0 new documents, 4 unchanged
skip finances: sitemap0.xml is empty and menus are rendered by script; awaiting decision
skip dgi: robots.txt answers 5xx and pages need script rendering; awaiting decision
skip marches_publics: portal suspended by the TGR for security reasons (7 Nov 2026)
```

Result in the database: 4 documents (4.5 M characters of Arabic text), 22 pack rules → 9 CGI articles,
1 `mentions` edge (BO n° 7556-bis, from the file name).

## Found by the real run

1. A BO PDF yields NUL bytes; PostgreSQL rejected the insert. Fixed and tested.
2. Arabic BO text from PyMuPDF moves numbers away from their words (`الجريدة الرسمية عدد` is followed by
   a date, not the issue number). An Arabic pattern would record wrong references, so none is used.

## Not done / honest limits

- The graph is thin today: only the Arabic BO home-page PDFs are reachable as static links. The useful
  texts (notes circulaires, CGI, lois de finances, CNC) are on DGI and finances.gov.ma, both script-rendered.
- No French BO edition (its list is script-loaded too).
- Marchés publics not crawled (portal suspended).
- No UI, no API endpoint, no agent reads the graph yet.

## Decisions needed

1. DGI and finances.gov.ma: request a permitted data access, or allow headless-browser rendering at a
   very low rate (robots.txt still respected; the DGI robots.txt currently answers 503, which this crawler
   treats as "no")?
2. Arabic texts: parse with the Unlimited-OCR adapter (Phase 6a) instead of PDF text, or use French sources only?
3. Approve adding ARCHITECTURE.md D.9 "Legal knowledge graph" and Phase 7a to Part G.
