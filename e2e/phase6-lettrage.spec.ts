// Phase 6b through the browser, real stack: a supplier invoice and its bank payment go through the
// normal monthly file (intake, proposal, statement, reconciliation, approval by a registered
// professional), then the expert letters the 4411 account, reverses the letter and letters again.
// No interception (Part K 26); API traffic logged.
import { mkdirSync, readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import { API_ORIGIN, EXPERT, loginThroughKeycloak, recordApiTraffic } from './stack';

const SHOTS = 'docs/reports/phase-6b';
mkdirSync(SHOTS, { recursive: true });
test.describe.configure({ mode: 'serial' });
const INVOICE = readFileSync('e2e/assets/invoice-text.pdf');
const COMPANY = `Draa Lettrage E2E ${Date.now().toString().slice(-6)}`;
const RIB = '007780000000000000050406';
const STATEMENT = `# Solde initial: 100000.00
# Solde final: 88000.00
Date,Libelle,Debit,Credit
2026-09-20,VIR FOURNISSEUR ATLAS FOURNITURES FAC-2026-0412,12000.00,0.00
`;

function bearerOf(page: Page): () => string {
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  return () => bearer;
}

async function logout(page: Page) {
  await page.getByTestId('btn-logout').click();
  await page.waitForURL((u) => u.pathname === '/');
}

test('accountant opens the company and its September file', async ({ page, request }) => {
  recordApiTraffic(page, 'phase6-accountant-setup');
  const bearer = bearerOf(page);
  await loginThroughKeycloak(page);
  await expect.poll(bearer).toMatch(/^Bearer ey/);
  const H = () => ({ Authorization: bearer(), 'Idempotency-Key': crypto.randomUUID() });
  const ice = `0098${Date.now().toString().slice(-11)}`;
  const client = await (await request.post(`${API_ORIGIN}/v1/client-entities`, { headers: H(), data: { legal_name: COMPANY, ice } })).json();
  const period = await (await request.post(`${API_ORIGIN}/v1/client-entities/${client.id}/periods`, {
    headers: H(), data: { period_code: '2026-09', starts_on: '2026-09-01', ends_on: '2026-09-30', fiscal_year_end: '2026-12-31' },
  })).json();
  expect((await request.post(`${API_ORIGIN}/v1/client-entities/${client.id}/chart-accounts/seed-cgnc`, { headers: H() })).status()).toBe(200);
  const wr = await request.post(`${API_ORIGIN}/v1/work-requests`, { headers: H(), data: { client_entity_id: client.id, accounting_period_id: period.id } });
  expect(wr.status()).toBe(201);
  await logout(page);
});

test('expert approves the VAT account', async ({ page }) => {
  recordApiTraffic(page, 'phase6-expert-mapping');
  await loginThroughKeycloak(page, { username: EXPERT });
  await page.getByRole('link', { name: 'Clients' }).click();
  await page.getByRole('link', { name: COMPANY }).click();
  const row = page.locator('[data-testid="tax-mapping-row"][data-slot="STANDARD_20/purchase"]');
  const option = row.locator('option', { hasText: /^34552 / });
  await row.locator('select').selectOption((await option.getAttribute('value')) ?? '');
  await expect(row.getByTestId('tax-mapping-state')).toContainText('Approuvé');
  await logout(page);
});

test('accountant books the invoice, reconciles the payment and requests approval', async ({ page }) => {
  test.setTimeout(5 * 60_000);
  const log = recordApiTraffic(page, 'phase6-accountant');
  await loginThroughKeycloak(page);
  await page.getByRole('link', { name: COMPANY }).click();
  await page.getByTestId('input-upload').setInputFiles({ name: 'facture-atlas.pdf', mimeType: 'application/pdf', buffer: INVOICE });
  await expect(page.getByTestId('msg-ok')).toContainText('facture-atlas.pdf lue', { timeout: 120_000 });
  await page.getByTestId('doc-row').filter({ hasText: 'facture-atlas.pdf' }).getByRole('button', { name: "Proposer l'écriture" }).click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'Écriture proposée' })).toBeVisible();

  await page.locator('input[name="rib"]').fill(RIB);
  await page.getByRole('button', { name: 'Ajouter le compte' }).click();
  await expect(page.getByTestId('select-bank-account')).toContainText('0406');
  await page.getByTestId('input-statement').setInputFiles({ name: 'releve-septembre.csv', mimeType: 'text/csv', buffer: Buffer.from(STATEMENT) });
  await expect(page.getByTestId('statement-row').filter({ hasText: 'releve-septembre.csv' })).toHaveAttribute('data-balance', 'ok');

  await page.getByTestId('link-reconciliation').click();
  await page.getByTestId('btn-generate-matches').click();
  const card = page.locator('[data-testid^="match-card-"]').first();
  await card.getByRole('button', { name: 'Rapprocher' }).click();
  await expect(page.getByTestId('msg-ok')).toContainText('Rapprochement accepté');
  await page.goBack();

  const ackButtons = page.locator('[data-testid^="btn-ack-"]');
  await expect(page.locator('[data-testid="issue-row"]').first()).toBeVisible();
  while ((await ackButtons.count()) > 0) {
    const id = ((await ackButtons.first().getAttribute('data-testid')) ?? '').replace('btn-ack-', '');
    await ackButtons.first().click();
    await page.getByTestId(`input-issue-${id}`).fill('Vérifié sur la facture et le relevé.');
    await page.getByTestId(`btn-issue-submit-${id}`).click();
    await expect(page.getByTestId(`btn-ack-${id}`)).toHaveCount(0);
  }
  await page.getByTestId('btn-request-approval').click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'Validation demandée' })).toBeVisible();
  await expect.poll(() => log.some((l) => /\/approvals -> 201/.test(l))).toBe(true);
  await logout(page);
});

test('expert approves the file, then letters, reverses and re-letters the supplier account', async ({ page }) => {
  const log = recordApiTraffic(page, 'phase6-expert');
  await loginThroughKeycloak(page, { username: EXPERT });

  // Fresh MFA login (under 5 minutes): the approval goes through without a step-up.
  await page.getByRole('link', { name: 'Validations' }).click();
  await page.getByRole('link', { name: COMPANY }).click();
  await page.getByRole('button', { name: 'Valider le dossier' }).click();
  await expect(page.getByTestId('msg-ok')).toContainText('Dossier validé');

  await page.getByRole('link', { name: 'Clients' }).click();
  await page.getByRole('link', { name: COMPANY }).click();
  const section = page.getByTestId('lettrage-section');
  await section.scrollIntoViewIfNeeded();
  await section.getByTestId('tab-supplier').click();
  const rows = section.getByTestId('open-item-row');
  await expect(rows).toHaveCount(2);
  await expect(section.getByTestId('balance-amount')).toHaveText(/^0,00$/);
  await page.screenshot({ path: `${SHOTS}/01-open-items.png`, fullPage: true });

  await section.getByTestId('btn-lettrage-generate').click();
  const proposal = section.getByTestId('lettrage-proposal');
  await expect(proposal).toHaveCount(1);
  await expect(proposal).toContainText('Montant identique');
  await expect(proposal).toContainText('12 000,00');
  await page.screenshot({ path: `${SHOTS}/02-proposal.png`, fullPage: true });

  await proposal.getByTestId('btn-lettrage-accept').click();
  await expect(section.getByTestId('msg-ok')).toContainText('Lettrage accepté');
  await expect(rows).toHaveCount(0);
  await expect(section.getByTestId('letter-code')).toHaveText('A');
  await page.screenshot({ path: `${SHOTS}/03-lettered.png`, fullPage: true });

  // Délettrage: a reason is mandatory, the lines reopen, the letter is not reused.
  await section.getByTestId('btn-lettrage-reverse').click();
  await expect(page.getByTestId('btn-reverse-confirm')).toBeDisabled();
  await page.getByTestId('input-reverse-reason').fill('Paiement à réaffecter après contrôle');
  await page.getByTestId('btn-reverse-confirm').click();
  await expect(section.getByTestId('msg-ok')).toContainText('Lettrage A annulé');
  await expect(rows).toHaveCount(2);

  // Manual lettrage of the same two lines, then acceptance: the next letter is B.
  for (const cb of await section.locator('input[type="checkbox"]').all()) await cb.check();
  await expect(section.getByTestId('selection-totals')).toContainText('Débit 12 000,00 · Crédit 12 000,00');
  await section.getByTestId('btn-lettrage-manual').click();
  await expect(section.getByTestId('lettrage-proposal')).toContainText('Lettrage manuel');
  await section.getByTestId('lettrage-proposal').getByTestId('btn-lettrage-accept').click();
  await expect(section.getByTestId('letter-code')).toHaveText('B');
  await expect(rows).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/04-relettered-B.png`, fullPage: true });

  for (const p of ['/open-items?account_class=supplier -> 200', '/lettrage-groups:generate -> 200', ':accept -> 200', ':reverse -> 200', '/lettrage-groups -> 201']) {
    await expect.poll(() => log.some((l) => l.includes(p)), { message: `expected API call: ${p}` }).toBe(true);
  }
});
