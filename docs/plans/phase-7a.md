# Phase 7a — Legal knowledge graph (sources, crawler, graph)

Founder request, 7 Nov 2026: use Scrapling (github.com/D4Vinci/Scrapling, 0.5.1) to collect Moroccan
legal and accounting texts and build a knowledge graph. The specialised agents (RAS, tax review,
payment terms) will read from this graph later. Scope chosen: plan + prototype.

## What this phase is and is not

- The graph is **evidence**, not rules. Nothing scraped ever becomes a value in `/jurisdiction/ma/`.
  A pack value changes only through the existing expert sign-off (Part I). The graph shows an expert
  which published texts mention the article a rule cites, so the sign-off is faster and traceable.
- No value (rate, threshold, deadline) is extracted from text. Extraction is deterministic and only
  finds **references**: laws, decrees, dahirs, notes circulaires, Bulletin Officiel numbers, CGI articles.
- No vector database (C.2). Plain PostgreSQL tables; full-text search can come later.
- Global, not tenant data: these are public texts. Tables have no `tenant_id`; the app role only reads.

## Sources (probed 7 Nov 2026 with Scrapling `Fetcher`, plain HTTP)

| Source | Finding | Prototype status |
|---|---|---|
| SGG — Bulletin Officiel (sgg.gov.ma) | Home page is static HTML with direct BO PDF links (`/BO/AR/3111/2026/BO_7556-bis_Ar.pdf`). The French BO list is loaded by script. No robots.txt (404 = allowed). | Crawled: home page + linked BO PDFs |
| DGI (tax.gov.ma) | Portal is IBM WebSphere; section pages (Notes circulaires, CGI, Décrets) are rendered by JavaScript, and the server answered 503 after two quick requests. robots.txt returns 503. | **Not crawled.** A 5xx robots.txt means "disallowed" in this crawler. Needs either a permitted API/export from the DGI or a decision to render pages in a browser |

**8 Nov 2026:** finances.gov.ma is now crawled with slow browser rendering; DGI rendering is enabled but blocked by its 503 robots.txt. See the report update.
| Finances (finances.gov.ma) — includes "Normalisation et profession comptable" (CNC) | robots.txt allows everything except `/_layouts/`, `/_vti_bin/`, `/_catalogs/`. The sitemap index points to `sitemap0.xml`, which is an empty `<urlset/>`; menus are rendered by SharePoint script | **Not crawled**: no static links to follow. Same decision as DGI |
| Marchés publics (marchespublics.gov.ma) | Portal suspended by the TGR "pour des raisons de sécurité" (503 notice) | **Not crawled** while suspended |

## Crawler rules (fixed in code, tested)

1. Respect robots.txt. 4xx robots = allowed; 5xx or unreachable = everything disallowed for that host.
2. One request at a time per host, minimum delay 5 s, identified User-Agent `AVENEL-KG/0.1`.
3. Plain `Fetcher` only. `StealthyFetcher` and anything that evades bot protection or CAPTCHAs is
   not used. A 403/429/503 stops that host for the run.
4. Every fetch is stored with URL, time, HTTP status, content type and SHA-256. Same URL + same hash is
   not stored twice; a changed document is a new row (append-only, like document versions).
5. Allowlisted hosts and path patterns only (`avenel/knowledge/sources.py`).

## Data (migration 012_knowledge_graph)

- `kg_documents` (append-only): source, url, fetched_at, http_status, content_type, sha256, title, text.
- `kg_nodes`: kind (`source`, `document`, `law`, `decree`, `dahir`, `circular`, `bo_issue`, `article`, `pack_rule`), key, label.
- `kg_edges`: from, to, kind (`published_by`, `mentions`, `cites_source`), document_id, evidence snippet.
- Grants: `avenel_app` SELECT and INSERT only (no UPDATE, no DELETE). The crawler (`scripts/kg_crawl.py`) runs as `avenel_app`.

## Graph built

- document → `published_by` → source
- document → `mentions` → law / decree / dahir / circular / bo_issue / article (with the matching sentence)
- pack_rule → `cites_source` → article (parsed from each pack entry's `source:` text, e.g. `CGI art. 106-II` → `CGI art. 106`)

So "which crawled texts mention the article behind `vat.deduction.cash_limit.basis`?" is one join.

## Tests (fixtures only, A.2.7)

- Robots handling (allowed, disallowed, 5xx), host stop on 503, allowlist, rate-limit delay (fake clock).
- Reference extraction golden cases (French and Arabic BO numbers, loi n° 9-88, décret n° 2-…, note circulaire n° …, CGI art. 106-II).
- Storage: dedup by hash, new version on change, documents append-only, app role read-only.
- Pack link: every pack `source:` that names a CGI article produces a `cites_source` edge.

A real sample crawl (SGG + finances, capped) is run once by hand and its request log is in the report.

## Decisions needed

1. DGI and finances.gov.ma: ask for a permitted data access, or allow browser rendering at a very low rate? (Not done without your answer.)
2. Marchés publics: revisit when the TGR portal is back.
3. ARCHITECTURE.md: add D.9 "Legal knowledge graph" and the Phase 7a entry in Part G after review.
