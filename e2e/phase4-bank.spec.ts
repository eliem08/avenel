// Phase 4 through the browser, real stack: register a bank account (RIB), import statements
// (balance check, balance break), and reconcile the payment with the invoice entry of the same file.
// Each run sets up its own company, September file and invoice entry, so the test can run again on a
// used stack (an invoice matched by an earlier run is not offered again). No interception (Part K 26);
// API traffic logged.
import { mkdirSync, readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { freshRib } from './rib';
import { API_ORIGIN, EXPERT, loginThroughKeycloak, recordApiTraffic } from './stack';

const SHOTS = 'docs/reports/phase-4';
mkdirSync(SHOTS, { recursive: true });
const INVOICE = readFileSync('e2e/assets/invoice-text.pdf');
const FILE = `Atlas Banque E2E ${Date.now()} SARL`;
// Synthetic RIB with a valid key, fresh each run (e2e/rib.ts).
const RIB = freshRib(); // unique per run (D-23)
// The statements carry a run reference so a reused stack does not refuse them as already received.
const RUN = Date.now().toString(36);
const GOOD = `# Solde initial: 100000.00
# Solde final: 88000.00
Date,Libelle,Debit,Credit
2026-09-20,VIR FOURNISSEUR ATLAS FOURNITURES FAC-2026-0412 R${RUN},12000.00,0.00
`;
const BROKEN = `# Solde initial: 50000.00
# Solde final: 49000.00
Date,Libelle,Debit,Credit
2026-09-25,FRAIS TENUE DE COMPTE R${RUN},150.00,0.00
`;

test('expert imports statements and reconciles the invoice payment', async ({ page, request }) => {
  const log = recordApiTraffic(page, 'phase4-expert');
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  test.setTimeout(5 * 60_000); // setup reads an invoice before the bank steps
  await loginThroughKeycloak(page, { username: EXPERT });

  // 0. Setup through the API with the expert's own token: a new company, its September file.
  await expect.poll(() => bearer).toMatch(/^Bearer ey/);
  const H = () => ({ Authorization: bearer, 'Idempotency-Key': crypto.randomUUID() });
  const client = await request.post(`${API_ORIGIN}/v1/client-entities`, { headers: H(), data: { legal_name: FILE, ice: `97${String(Date.now()).slice(-13)}` } });
  expect(client.status(), await client.text()).toBe(201);
  const clientId = ((await client.json()) as { id: string }).id;
  const period = await request.post(`${API_ORIGIN}/v1/client-entities/${clientId}/periods`, {
    headers: H(), data: { period_code: '2026-09', starts_on: '2026-09-01', ends_on: '2026-09-30', fiscal_year_end: '2026-12-31' },
  });
  expect(period.status(), await period.text()).toBe(201);
  expect((await request.post(`${API_ORIGIN}/v1/client-entities/${clientId}/chart-accounts/seed-cgnc`, { headers: H() })).status()).toBe(200);
  const wr = await request.post(`${API_ORIGIN}/v1/work-requests`, { headers: H(), data: { client_entity_id: clientId, accounting_period_id: ((await period.json()) as { id: string }).id } });
  expect(wr.status(), await wr.text()).toBe(201);

  // The 20 % purchase VAT account is approved by the expert in the page, then the invoice is read and
  // its entry proposed (by the bookkeeping agent or the button, whichever comes first).
  await page.getByRole('link', { name: 'Clients' }).click();
  await page.getByRole('link', { name: FILE }).click();
  const vatRow = page.locator('[data-testid="tax-mapping-row"][data-slot="STANDARD_20/purchase"]');
  const option = vatRow.locator('option', { hasText: /^34552 / });
  await vatRow.locator('select').selectOption((await option.getAttribute('value')) ?? '');
  await expect(vatRow.getByTestId('tax-mapping-state')).toContainText('Approuvé');
  await page.getByRole('link', { name: 'File de travail' }).click();
  await page.getByRole('link', { name: FILE }).click();
  await page.getByTestId('input-upload').setInputFiles({ name: 'facture-atlas.pdf', mimeType: 'application/pdf', buffer: INVOICE });
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'facture-atlas.pdf lue' })).toBeVisible({ timeout: 120_000 });
  await page.getByTestId('doc-row').filter({ hasText: 'facture-atlas.pdf' }).getByRole('button', { name: "Proposer l'écriture" }).click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: /Écriture (déjà )?proposée/ })).toBeVisible();

  // 1. Bank account: RIB validated by the API, shown masked only
  await page.locator('input[name="rib"]').fill(RIB);
  await page.getByRole('button', { name: 'Ajouter le compte' }).click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'enregistré' })).toBeVisible();
  await expect(page.getByTestId('select-bank-account')).toContainText(RIB.slice(-4));
  await expect(page.getByTestId('select-bank-account')).not.toContainText(RIB);

  // 2. A statement whose balances agree, then one whose balances do not
  await page.getByTestId('input-statement').setInputFiles({ name: `releve-septembre-${RUN}.csv`, mimeType: 'text/csv', buffer: Buffer.from(GOOD) });
  await expect(page.getByTestId('statement-row').filter({ hasText: `releve-septembre-${RUN}.csv` })).toHaveAttribute('data-balance', 'ok');
  await page.getByTestId('input-statement').setInputFiles({ name: `releve-errone-${RUN}.csv`, mimeType: 'text/csv', buffer: Buffer.from(BROKEN) });
  await expect(page.getByTestId('statement-row').filter({ hasText: `releve-errone-${RUN}.csv` })).toHaveAttribute('data-balance', 'break');
  await expect(page.getByTestId('msg-error')).toContainText('les soldes ne concordent pas');
  await expect(page.getByTestId('issue-strip')).toContainText('bloquante');
  await page.getByTestId('statements-table').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOTS}/01-statements-balance-check.png`, fullPage: true });

  // Same statement again: recognised as already received, not imported twice
  await page.getByTestId('input-statement').setInputFiles({ name: `releve-septembre-copie-${RUN}.csv`, mimeType: 'text/csv', buffer: Buffer.from(GOOD) });
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'déjà été reçu' })).toBeVisible();
  await expect(page.getByTestId('statement-row')).toHaveCount(2);
  await expect(page.getByTestId('statement-row').filter({ hasText: `releve-septembre-copie-${RUN}.csv` })).toHaveCount(0);

  // 3. Reconciliation: the 12 000,00 payment is matched to the invoice entry and accepted
  await page.getByTestId('link-reconciliation').click();
  await expect(page.getByTestId('reconciliation-screen')).toBeVisible();
  await page.getByTestId('btn-generate-matches').click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'rapprochement' })).toBeVisible();
  const card = page.locator('[data-testid^="match-card-"]').first();
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Rapprocher' }).click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'Rapprochement accepté' })).toBeVisible();
  // The screen itself must show the decision (it used to reload before the commit landed).
  await expect(page.getByTestId('reconciliation-screen')).toContainText('1 / 1 rapprochés');
  await page.screenshot({ path: `${SHOTS}/02-reconciliation-accepted.png`, fullPage: true });

  // Through the API: exactly one accepted match for the bank line, for the full amount
  const wrId = page.url().split('/files/')[1].split('/')[0];
  const matches = (await (await request.get(`${API_ORIGIN}/v1/reconciliation/matches?work_request_id=${wrId}`, { headers: { Authorization: bearer } })).json()) as {
    status: string;
    difference_mad: number;
    items: { bank_transaction_id: string | null; amount_mad: number }[];
  }[];
  const accepted = matches.filter((m) => m.status === 'accepted');
  console.log(`[phase4-expert] matches=${matches.length} accepted=${accepted.length} difference=${accepted[0]?.difference_mad}`);
  expect(accepted).toHaveLength(1);
  expect(accepted[0].difference_mad).toBe(0);

  for (const p of ['POST http://localhost:8000/v1/bank-accounts -> 201', '/bank-statements/upload -> 201', '/bank-statements/upload -> 200', '/reconciliation/generate -> 201', '/accept -> 200']) {
    await expect.poll(() => log.some((l) => l.includes(p)), { message: `expected API call: ${p}` }).toBe(true);
  }
});
