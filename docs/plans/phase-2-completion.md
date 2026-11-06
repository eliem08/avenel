# Phase 2 completion — intake and reading, through the real stack

Status: in progress (human instruction 6 Nov 2026: "Start Phase 2"). Stops for review at the exit criteria.

## Reality check (6 Nov 2026, API driven with a real Keycloak token against docker-compose)

| Step | Before | After fixes (commit 56ab3ea) |
|---|---|---|
| Browser → storage | Impossible: filesystem backend linked to a non-existent `/v1/storage/uploads` route; MinIO images no longer published | `PUT /v1/documents/{id}/content` (human decision): size + SHA-256 verified against the init declaration, write-once |
| API storage dir | `PermissionError` on `/app/storage_data` (non-root container) → every upload 500 | Volume at `/var/lib/avenel/storage` owned by the app user |
| ClamAV | clamd kept the image's March 2026 signatures; freshclam could not notify it → intake paused | freshclam notifies clamd over TCP; health gate requires `intake_paused:false` and asks clamd to reload |
| OCR in container | `libxcb.so.1` missing → OpenCV/RapidOCR import failed → caught silently → PDF bytes decoded as text → empty extraction, `status: read`, 200 | Libraries added; real text and scanned PDFs read (invoice no., date, ICEs, IF, RC, HT/TVA/TTC with normalized bboxes) |
| Failure visibility | Render/OCR failures swallowed | Real PDF that cannot render → 422; OCR engine unavailable → 503; nothing half-written (tests fail on the old code) |
| Page images for the viewer | JSON link to a non-existent `/v1/storage/files` route | `GET /v1/documents/{id}/pages/{n}/image` (PNG, scope-first) |
| Worker | Sleep loop | Not needed: processing runs inline in `complete-upload` (stated as such) |

## Remaining work

1. **Monthly file screen** (`/files/:id` from a Queue row): header, documents table (file, type, status), upload (FileDrop: init → content → complete-upload), intake-paused and quarantine messages as the API returns them, open issues for the file.
2. **Document review screen** (`/documents/:id`): page image with field boxes (Part E.5: focusing a field draws a 2 px sky box over its source region, 160 ms, disabled under reduced motion), field list with "à confirmer" for low confidence, correction (`PATCH /extraction`, "Confirmer"), validation issues.
3. **Accuracy report** (Part G exit): run the evaluation harness on all 300 synthetic fixtures and write `docs/benchmarks/phase-2-accuracy-report.md` (field-level exact match, per language). States that the documents are synthetic.
4. **Residency router** (exit): confirm tests show disallowed calls refused and that the suite makes no provider calls; add any missing case.
5. **E2E (real stack):** accountant uploads the scanned PDF in the browser, sees it read, opens it, sees the page and a field box, corrects a field, sees the change persisted; EICAR upload is quarantined with a blocking issue; client user cannot open another company's document. Every API request logged.
6. `make ci` + GitHub CI green, report `docs/reports/phase-2-completion-report.md`. Stop.

## Exit criteria (Part G Phase 2)

- Field-level accuracy report generated on the 300-document fixture set.
- Residency router refuses disallowed calls.
- No provider call in tests.
- Plus (5c-1 rule): every Phase 2 capability shown working in the browser against the real stack, with the API request log.
