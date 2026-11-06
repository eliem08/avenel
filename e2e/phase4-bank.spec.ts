// Phase 4 through the browser, real stack: register a bank account (RIB), import statements
// (balance check, balance break), and reconcile the payment with the invoice entry proposed in the
// Phase 3 test (same company, same run). No interception (Part K 26); API traffic logged.
import { mkdirSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { API_ORIGIN, EXPERT, loginThroughKeycloak, recordApiTraffic } from './stack';

const SHOTS = 'docs/reports/phase-4';
mkdirSync(SHOTS, { recursive: true });
const FILE = 'Atlas Distribution SARL';
// Synthetic RIB with a valid key (computed with avenel.bank.rib.compute_moroccan_rib_key).
const RIB = '007780000000000000050406';
const GOOD = `# Solde initial: 100000.00
# Solde final: 88000.00
Date,Libelle,Debit,Credit
2026-09-20,VIR FOURNISSEUR ATLAS FOURNITURES FAC-2026-0412,12000.00,0.00
`;
const BROKEN = `# Solde initial: 50000.00
# Solde final: 49000.00
Date,Libelle,Debit,Credit
2026-09-25,FRAIS TENUE DE COMPTE,150.00,0.00
`;

test('expert imports statements and reconciles the invoice payment', async ({ page, request }) => {
  const log = recordApiTraffic(page, 'phase4-expert');
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  await loginThroughKeycloak(page, { username: EXPERT });
  await page.getByRole('link', { name: FILE }).click();

  // 1. Bank account: RIB validated by the API, shown masked only
  await page.locator('input[name="rib"]').fill(RIB);
  await page.getByRole('button', { name: 'Ajouter le compte' }).click();
  await expect(page.getByTestId('msg-ok')).toContainText('enregistré');
  await expect(page.getByTestId('select-bank-account')).toContainText('0406');
  await expect(page.getByTestId('select-bank-account')).not.toContainText(RIB);

  // 2. A statement whose balances agree, then one whose balances do not
  await page.getByTestId('input-statement').setInputFiles({ name: 'releve-septembre.csv', mimeType: 'text/csv', buffer: Buffer.from(GOOD) });
  await expect(page.getByTestId('statement-row').filter({ hasText: 'releve-septembre.csv' })).toHaveAttribute('data-balance', 'ok');
  await page.getByTestId('input-statement').setInputFiles({ name: 'releve-errone.csv', mimeType: 'text/csv', buffer: Buffer.from(BROKEN) });
  await expect(page.getByTestId('statement-row').filter({ hasText: 'releve-errone.csv' })).toHaveAttribute('data-balance', 'break');
  await expect(page.getByTestId('msg-error')).toContainText('les soldes ne concordent pas');
  await expect(page.getByTestId('issue-strip')).toContainText('bloquante');
  await page.getByTestId('statements-table').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOTS}/01-statements-balance-check.png`, fullPage: true });

  // Same statement again: recognised as already received, not imported twice
  await page.getByTestId('input-statement').setInputFiles({ name: 'releve-septembre-copie.csv', mimeType: 'text/csv', buffer: Buffer.from(GOOD) });
  await expect(page.getByTestId('msg-ok')).toContainText('déjà été reçu');
  await expect(page.getByTestId('statement-row')).toHaveCount(2);

  // 3. Reconciliation: the 12 000,00 payment is matched to the invoice entry and accepted
  await page.getByTestId('link-reconciliation').click();
  await expect(page.getByTestId('reconciliation-screen')).toBeVisible();
  await page.getByTestId('btn-generate-matches').click();
  await expect(page.getByTestId('msg-ok')).toContainText('rapprochement');
  const card = page.locator('[data-testid^="match-card-"]').first();
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Rapprocher' }).click();
  await expect(page.getByTestId('msg-ok')).toContainText('Rapprochement accepté');
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
