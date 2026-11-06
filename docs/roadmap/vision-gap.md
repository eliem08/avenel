# AVENEL vision vs what is built (7 November 2026)

**Sources:** the founder's business documents `AVENEL_ameliore.docx` (concept and phased strategy) and `p ilyass.docx` (original concept with French additions). **Binding spec:** `ARCHITECTURE.md` (Part B.3 pilot scope). This file is a roadmap note, not a spec change: anything outside B.3 needs a human decision and an ARCHITECTURE.md update before it is built (Part A).

Status key: **Built** = works in the browser on the real stack and is covered by CI · **Partial** · **Not started** · **Excluded by B.3** (needs a scope decision).

## 1. Core service — "AVENEL Services" (monthly file, review-ready)

| Vision item | Status | Where / what is missing |
|---|---|---|
| Receive, identify, organise documents (multi-channel) | Partial | Console + portal upload, ClamAV, duplicates, OCR, classification (Phase 2). No e-mail/WhatsApp intake. |
| Extract data, flag duplicates / missing fields / inconsistencies | Built | Phase 2–3 (exact + probable duplicates, D.6 validation). Accuracy proven on synthetic data only. |
| Proposed classifications and entries linked to sources | Built | Phase 3 (purchases from real scans; sales, credit notes, fixed assets via golden tests). |
| Bank reconciliation | Built | Phase 4 (incl. withheld VAT at service level). Real bank PDFs not yet seen. |
| Customer and supplier account matching (lettrage), partial settlements, outstanding balances | Built (Phase 6b) | Exact matching only until an expert sets tolerances; see docs/reports/phase-6b.md. |
| Exception list and client requests | Built | Issues queue, acknowledge, send to client, portal (Phase 5). |
| Review package with evidence | Built | Approval, Sage/Odoo export, evidence pack (Phase 5). Round trip with real Sage/Odoo pending. |
| **Draft financial statements: bilan, compte de produits et charges (CPC), tableau des immobilisations, other états de synthèse** | **Not started** | Requires a full trial balance and opening balances (AVENEL is a monthly preparation layer, not the books — B.1), plus CGNC statement models confirmed by an expert. |

## 2. "AVENEL Agents"

| Agent | Status | Notes |
|---|---|---|
| Document Intake | Partial | Local OCR + rules; no LLM (no provider implemented; router returns a placeholder when allowed). |
| Bookkeeping (entries) | Partial | Rule-based entry builder; account suggester uses counterparty history. |
| Reconciliation | Built (rules) | Candidate generation + difference kinds. |
| Quality Control | Partial | D.6 validation + approval quality gate. |
| Client Communication | Partial | Requests sent from the issues list; no e-mail/SMS sending. |
| **Customer Accounting** (receivables, matching, balances) | **Not started** | Depends on lettrage (above). |
| **Supplier Accounting** (payables, payment matching, discrepancies) | **Not started** | Same. |
| **Tax Review** (checks, **retenue à la source** with its complexities) | Partial | VAT and IS/VAT withholding in reconciliation; no standalone tax review, no RAS on salaries/fees/rents, no declaration preparation. |
| **Payment Terms** (délais de paiement monitoring, delays, follow-up) | **Not started** | Needs due dates (field exists in extraction) and the legal payment-term rules in the pack (`needs_expert`). |
| **Payment Preparation** (batches for approval) | **Excluded by B.3** ("paying anything" out of scope); preparation without execution would need a scope decision. |
| Reporting (statements, summaries, dashboards) | Not started | Only internal review-effort metrics exist. |
| Central orchestration with permissions and escalation | Partial | Explicit workflow state machine (Part D.1); worker is a sleep loop; no agent runtime. |

## 3. Tax knowledge base

| Vision item | Status | Notes |
|---|---|---|
| Versioned rules with effective dates and sources | Built | Jurisdiction pack (`jurisdiction/ma/*.yaml`), loader, schema. |
| Published rule vs interpretation; version applied per file | Partial | Pack version stored per period; `source_cited` / `needs_expert` / `verified` statuses (Phase 3). |
| **Finance laws, circulars, special cases; daily monitoring of new publications** | **Not started** | No ingestion of Lois de finances / notes circulaires, no monitoring job, no review workflow for pack updates. 78 rules still need a professional's signature. |

## 4. "AVENEL API" (partners)

| Vision item | Status | Notes |
|---|---|---|
| Expose extraction, classification, reconciliation, status to fintechs/ERPs/banks | **Excluded by B.3** ("a public partner API") | The internal REST API exists (OpenAPI 3.1), but no partner auth (client credentials), quotas, billing or partner tenancy. |

## 5. Beyond accounting

| Vision item | Status |
|---|---|
| **Comptabilité analytique, contrôle de gestion, budget vs actual, margins, cash flow, decision dashboards** | **Not started** — not in ARCHITECTURE.md. |
| **Public procurement (marchés publics)**: milestones, contracts and amendments, invoice-to-contract matching, payment documentation, specific accounting for public establishments, public companies and bidders | **Not started** — not in ARCHITECTURE.md; needs the applicable public accounting framework and procurement rules validated by experts. |
| Automation / AI consulting line | Business activity, not software. |
| International | Excluded by B.3 (Morocco only). |

## 6. KPIs named in the documents

| KPI | Status |
|---|---|
| Review effort / time per file, entries edited, fields corrected | Partial (`review_effort_metrics`, internal metrics screen not routed) |
| Accountant acceptance rate of proposed entries | Not measured yet (edits and revisions are recorded, so it can be derived) |
| Share of files completed without intervention, exception and rework rates | Not measured |
| Cost per accepted file, provider cost, margin | Partial (provider_calls costs; no billing view) |
| MRR, CAC, retention | Not in product (business metrics) |

## Suggested order (follows the documents' own phases)

The documents put the core monthly file first (their Phases 1–3 = ARCHITECTURE Part G 1–5, now built), then **Phase 4 "broader financial operations"**. A sensible next scope, each needing an ARCHITECTURE.md decision first:

1. **Lettrage** (customer and supplier open items, partial settlements, balances) — natural extension of Phase 4 reconciliation; unlocks the customer/supplier accounting agents.
2. **Payment terms monitoring** (délais de paiement) — due dates are already extracted; needs the legal rules in the pack.
3. **Retenue à la source review** beyond VAT/IS withholding, with a reviewed knowledge base of finance-law and circular references.
4. **Draft états de synthèse** (bilan, CPC, immobilisations) — requires a decision on opening balances / trial balance, since AVENEL is not the books.
5. Then management control dashboards, the partner API, and the public procurement module as separate products.

None of these replaces the open pilot items: Sage/Odoo round trip, expert sign-off, real anonymised documents and bank statements, production hosting.
