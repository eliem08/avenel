# Phase 6 plan — Lettrage, Unlimited-OCR, specialised agents (draft, awaiting approval)

Requested by the founder on 7 November 2026: "yes [lettrage first] and for ocr use baidu Unlimited-OCR and use very specialised agents with SOTA architectures". Nothing here is built yet. Items marked **ARCH** change ARCHITECTURE.md and need explicit approval first (Part A).

## 6a. OCR engine: Baidu Unlimited-OCR (local)

- **What it is:** an open-source (MIT) OCR model from Baidu, `baidu/unlimited-ocr` (June 2026), with a version 2, `baidu/Unlimited-OCR-2` (October 2026). It parses long multi-page PDFs in one pass, and is served through vLLM or SGLang. I have only read secondary coverage so far. Before it is pinned, I will check the repo, the licence, the weights hash and the hardware needs at the source.
- **Fit with ARCHITECTURE.md:** C.3 already says the OCR runs locally, in a container, behind an adapter, for `MA_ONLY` tenants. A self-hosted Unlimited-OCR is allowed under that rule; Baidu's cloud API is not, because it would be a cross-border transfer under Loi 09-08. **ARCH:** the C.3 OCR row would change from "docTR or PaddleOCR" to "Unlimited-OCR (self-hosted); PaddleOCR as CPU fallback".
- **Work:**
  - New adapter, `avenel/providers/ocr_unlimited.py`. It returns text, layout and bboxes in the existing `OcrResult` shape, and fails loudly (`OcrUnavailableError`).
  - The compose service gets a pinned image with its digest.
  - Every call is recorded in `provider_calls`.
  - Recorded responses serve as test fixtures (Part A rule 7: no live provider in tests).
- **Proof:** rerun the Phase 2 accuracy report on the same fixture set. Then compare the current engine with Unlimited-OCR field by field, including Arabic and French pages.
- **Blocker (your decision):** vLLM needs an NVIDIA GPU. This laptop and the GitHub CI runners have none. Options: (1) a GPU host in Morocco for pilot and production; (2) run it only on a GPU dev machine and keep the CPU engine in CI; (3) a CPU build, if the model supports one (it would be slow). Until this is decided, CI keeps the current engine and uses recorded Unlimited-OCR fixtures.
- **Decision (7 Nov 2026): CPU only for now.** The current CPU engine stays the default everywhere. The Unlimited-OCR adapter is built behind a setting that is off by default and tested only against recorded responses. It is switched on, and the accuracy comparison is run, once a GPU host exists.

## 6b. Lettrage (customer and supplier open items)

- **ARCH:**
  - Add lettrage to the B.3 scope.
  - New tables (new migration 011; applied migrations stay untouched): `open_items`, which holds the remaining balance for each 342x/441x line, and `lettrage_matches`, which links N invoices to M payments and records partial amounts, a letter code, status, proposer and approver.
- **Matching:** deterministic candidates (counterparty ICE, amount sums including subset-sum within limits, references, date window). An agent may explain a candidate; it never chooses the match (rule in D.x, kept).
- **Partial settlements:** a match leaves a remaining balance. Lettrage needs an accountant's approval, can be reversed by a new delettrage record, and is never deleted.
- **Not invented:** tolerance thresholds for rounding and FX differences, and their accounts. These go to `needs_expert` in the pack.
- **UI:** an "Open items" tab per client, showing aged balance, proposals, accept/reject and partial-match details.
- **Proof:** golden tests (one invoice paid in 2 instalments, one payment covering 3 invoices, a credit note), plus a real-stack Playwright test with the API log.

## 6c. Specialised agent architecture

These are your agents, specialised and kept within the rules that already exist (C.6, D):

- **Agents and their contracts.** One agent per function, each with a narrow, typed contract:
  - Intake/Classifier, Extractor, Bookkeeping, Customer accounting, Supplier accounting, Reconciliation, QC
  - Later phases: Tax review/RAS, Payment terms
- **How each agent works:**
  - A JSON Schema for input and output, validated on every call.
  - A whitelist of the tools it may call.
  - A confidence score, an evidence citation (document, page, bbox) and an escalation rule.
- **Orchestration:** the existing explicit state machine (D.1) plus Procrastinate jobs, rather than free-form agent chat. Each agent step is a durable job, so it can be retried, is idempotent and is audited.
- **Current state-of-the-art methods:**
  - Structured outputs or constrained decoding.
  - Retrieval over the versioned jurisdiction pack, where every citation must point to a rule ID.
  - A verifier pass: a second model, or deterministic checks, re-validates each output before a human sees it.
  - Self-consistency voting on low-confidence fields.
  - An evaluation harness per agent, scored against the fixture set and tracked in CI, so a regression fails the build.
  - Accountant corrections are stored as labelled data for later fine-tuning or few-shot use.
- **Hard limits (unchanged):**
  - Money, totals and matches are computed by code, not by a model.
  - No agent approves, pays or files.
  - Tax values come only from pack rules with sources.
- **Models:** `MA_ONLY` tenants need a local or Morocco-hosted LLM, served the same way as the OCR (vLLM on the same GPU host, model to choose, for example Qwen3 or Llama class). Hosted frontier models (for example Claude) only for tenants with `EU_ALLOWED` or wider and a CNDP declaration. **Your decision:** which model and host.

## Order and exits

1. 6a adapter, with a fixture-based accuracy comparison. Exit: report, and CI green.
2. 6b lettrage. Exit: browser proof on the real stack, with the API log.
3. 6c agent runtime, starting with the Customer and Supplier accounting agents on top of lettrage. Exit: eval-harness scores reported, and no provider call in tests.

Stop for review after each.

## Decisions needed before building

1. Approve the ARCHITECTURE.md changes (OCR row, lettrage scope, agent runtime).
2. GPU host: Morocco cloud, local GPU machine, or CPU only for now.
3. LLM model and host for `MA_ONLY` tenants.
4. An expert to set the lettrage tolerances and their accounts.
