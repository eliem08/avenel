# AVENEL — Implementation status

**Last audit:** 11 November 2026, on branch `main` at commit `0218453` plus the changes of this cycle.
**Reference documents:** `ARCHITECTURE.md` (binding spec) and the founder's two business documents
(`AVENEL_ameliore.docx`, `p ilyass.docx`). The file `AVENEL_MASTER_ARCHITECTURE_v2.md` named in the CTO brief
does not exist in the repository; `ARCHITECTURE.md` is the master architecture.

Status words: **Works** = code exists, automated tests ran and passed in this audit. **Partial** = works for
part of the need, the gap is stated. **Not built** = no working code. Nothing here is proven on real client
data unless the line says so.

## Checks run in this audit (11 November 2026)

| Check | Result |
|---|---|
| Python tests (`pytest`, real PostgreSQL 16) before the change | 327 passed |
| Python tests after the change | see the cycle report in `docs/reports/cto-cycle-1.md` |
| `ruff check avenel apps scripts` | passed |
| `mypy avenel apps/api scripts` | passed (100 files) |
| Tax-literal guard, migration-hash guard | passed |
| Frontend unit tests (`vitest`) | 47 passed |
| Frontend type check and ESLint | passed |
| Browser tests (Playwright, 8 files) | **not run in this audit**; last green run was CI on commit `74fb0ad` |
| Front-end production build, OpenAPI lint, RLS check | **not run in this audit** |

## Bookkeeping workflow (the first product)

| Step | Status | Evidence / gap |
|---|---|---|
| Document intake (console and client portal upload) | Works | No e-mail or WhatsApp intake. |
| Secure storage (write-once originals, hash checked) | Works | S3 or filesystem backend. Object lock not enforced (documented gap, pilot-1 report). |
| Malware scan | Works | ClamAV; intake pauses when the scanner is down or stale. |
| Reading (OCR) and extraction | Partial | Local OCR and rules only. **No AI provider is connected**: the router records and refuses or returns nothing. Accuracy measured on synthetic documents only. |
| Deterministic validation (D.6) | Works | |
| Duplicate detection (exact and probable) | Works | |
| Accounting classification | Partial | Rule-based; account suggestion from counterparty history. |
| Proposed journal entries | Works | Balanced by a database trigger and property tests. Purchases from scans; sales, credit notes and fixed assets by golden tests only. |
| Bank reconciliation | Works | Includes VAT withheld at source. No real bank PDF seen yet. |
| Customer / supplier matching (lettrage) | Works | Exact amounts only until an expert sets tolerances. |
| Exception handling (issues, client requests) | Works | No e-mail or SMS sending. |
| Quality control | Partial | Validation plus the approval quality gate. No separate QC agent. |
| Accountant approval (subject hash, separation of duties, MFA) | Works | |
| Export (Sage 100 CSV/PNM, Odoo CSV, evidence pack) | Works | Round-trip import into a real Sage or Odoo not yet done. |
| Background processing with retries | Partial (since 11 Nov 2026) | Job queue (migration 014) and a real worker: retries with backoff, 4 attempts, then a blocking issue. Used when the reading engine is down (upload answers 202, the worker retries). Since 11 Nov 2026 every reading can go through the queue (`AVENEL_READ_IN_BACKGROUND=1`, off by default because nothing reads without a running worker); the file screen then follows the document's status until it is read. Background mode tested with pytest and the worker, not yet on the Docker stack. Proven on the Docker stack on 11 Nov 2026 with jobs queued directly (see `docs/reports/cto-cycle-2.md`); the 202 path was not triggered on the stack. |
| Idempotent mutating requests | Works since this cycle | Now durable and per tenant (ADR-003). |

## Cross-cutting

| Area | Status | Note |
|---|---|---|
| Tenant isolation (app checks + forced RLS) | Works | Cross-tenant tests on every endpoint. |
| Audit chain, append-only evidence | Works | Verified by tests. |
| Jurisdiction pack (versioned tax rules) | Partial | 40 rules `needs_expert` (disabled) and 48 `source_cited` ("à confirmer"); the expert's work list is `docs/pilot/AVENEL-travail-expert.docx` (`scripts/generate_expert_docx.py`); rules awaiting a Moroccan professional's signature are disabled. |
| Knowledge graph of legal sources | Partial | 842 French gazette issues (1994–2026), 60 finances.gov.ma documents stored. 1912–1994 crawl in progress. tax.gov.ma blocked by its own robots.txt. Evidence only; never sets a tax value. |
| Backup and restore drill | Works | Off-host replication is simulated (pilot-2 report). |

## Not built (long-term areas of the vision)

Financial statements (bilan, CPC, fixed-asset schedule) · tax review agent and RAS on fees, rents and salaries ·
payment terms monitoring · payment preparation · management control (analytics, budgets, dashboards) ·
public procurement · partner API · ERP and bank connectors. See `ARCHITECTURE_GAP_ANALYSIS.md`.
