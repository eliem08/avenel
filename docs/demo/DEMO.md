# AVENEL live demo (local stack)

About 10 minutes. Everything runs on this computer: Keycloak login with a one-time code, the API, the worker,
real ClamAV, OCR. No AI provider is connected yet (B-02): reading uses rules and OCR, which works well on the demo invoice.

## Before the demo (5 minutes)

1. Start Docker Desktop. Check the stack: `docker ps` shows avenel-api, avenel-worker, avenel-postgres, avenel-keycloak, avenel-clamav.
2. Start the web app: `npx vite --port 5173 --strictPort` (from the repo root).
3. Create a fresh demo company: `npx playwright test e2e/demo-setup.spec.ts`, then note the printed name (`Société Démo … SARL`).
4. Keep `docs/demo/facture-demo.pdf` at hand (a scanned purchase invoice, FAC-2026-0412, 12 000 MAD TTC).
5. Virus signatures must be under 48 h old, or uploads pause (by design). If intake says paused: `docker restart avenel-freshclam`.

## Logging in

Open http://localhost:5173, click "Se connecter". Passwords are in `docker/keycloak/realm-export-test.json`.
For the one-time code, run `node scripts/demo-otp.mjs` and type the code shown for the user (it changes every 30 s).
Use **ci-expert@test.internal**: a registered professional, so it can approve accounts.

## The story

1. **Work queue (File de travail).** Every client's monthly file, with its status.
2. **Client page (Clients → Société Démo …).** Click "Importer le plan CGNC": the chart of accounts loads.
   In the VAT accounts table, row "20 % achats", pick 34552: it shows "Approuvé par CI Expert".
   The point: no tax mapping is used until a professional has approved it, and the approval is signed and audited.
3. **Monthly file (File de travail → Société Démo …).** Upload `facture-demo.pdf`.
   The file is checked by ClamAV, then read in the background; the status moves to "lue" in a few seconds.
4. **Review the document.** Open it: the page image, and the fields read by OCR (number, supplier ICE, totals).
   Click a field: a box shows where the value is on the page. Correct a value: the correction is recorded.
5. **Proposed entry.** Back on the file, click "Proposer l'écriture", then open the review:
   a balanced entry (debit = credit = 12 000), with VAT on 34552 and the supplier on 4411; clicking a line shows its evidence on the invoice.
6. **Security, if asked.**
   - Log in as ci-client@test.internal: that client only sees Atlas, and another company's document is "introuvable".
   - Any upload of a virus test file is quarantined, with a blocking anomaly.

## Limits to say out loud

- Tax rules: 40 are disabled until a Moroccan expert signs them (`docs/pilot/AVENEL-travail-expert.docx`), and 48 are shown "à confirmer".
- No AI provider yet; accuracy on real client documents is not measured yet (B-03).
- This dev stack holds data from earlier test runs (other "Atlas E2E …" companies): show only the Société Démo company.
