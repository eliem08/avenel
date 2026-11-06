// Phase 5 through the browser, real stack: preparation by the accountant, approval by a registered
// professional with a REAL MFA step-up (the session is let age past 5 minutes, Part K 5), then the
// Sage export is generated and downloaded. No interception (Part K 26); API traffic logged.
import { mkdirSync, readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import { API_ORIGIN, EXPERT, currentTotp, loginThroughKeycloak, recordApiTraffic } from './stack';

const SHOTS = 'docs/reports/phase-5';
mkdirSync(SHOTS, { recursive: true });
test.describe.configure({ mode: 'serial' });
const INVOICE = readFileSync('e2e/assets/invoice-text.pdf');
const COMPANY = `Souss Fournitures E2E ${Date.now().toString().slice(-6)}`;
const STEP_UP_WAIT_MS = 305_000; // Part K 5: approval needs an MFA login no older than 300 s

function bearerOf(page: Page): () => string {
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  return () => bearer;
}

test('accountant prepares a file and requests approval', async ({ page, request }) => {
  recordApiTraffic(page, 'phase5-accountant');
  const bearer = bearerOf(page);
  await loginThroughKeycloak(page);
  await expect.poll(bearer).toMatch(/^Bearer ey/);
  const H = () => ({ Authorization: bearer(), 'Idempotency-Key': crypto.randomUUID() });

  // Setup through the real API with the accountant's own token (no UI for "Nouveau dossier" yet)
  const ice = `0099${Date.now().toString().slice(-11)}`;
  const client = await (await request.post(`${API_ORIGIN}/v1/client-entities`, { headers: H(), data: { legal_name: COMPANY, ice } })).json();
  const period = await (await request.post(`${API_ORIGIN}/v1/client-entities/${client.id}/periods`, {
    headers: H(), data: { period_code: '2026-09', starts_on: '2026-09-01', ends_on: '2026-09-30', fiscal_year_end: '2026-12-31' },
  })).json();
  expect((await request.post(`${API_ORIGIN}/v1/client-entities/${client.id}/chart-accounts/seed-cgnc`, { headers: H() })).status()).toBe(200);
  const wr = await request.post(`${API_ORIGIN}/v1/work-requests`, { headers: H(), data: { client_entity_id: client.id, accounting_period_id: period.id } });
  expect(wr.status()).toBe(201);
  process.env.E2E_P5_CLIENT = client.id;
  process.env.E2E_P5_WR = (await wr.json()).id;
  await page.getByTestId('btn-logout').click();
  await page.waitForURL((u) => u.pathname === '/');
});

test('expert approves the VAT account for the new company', async ({ page }) => {
  recordApiTraffic(page, 'phase5-expert-mapping');
  await loginThroughKeycloak(page, { username: EXPERT });
  await page.getByRole('link', { name: 'Clients' }).click();
  await page.getByRole('link', { name: COMPANY }).click();
  const row = page.locator('[data-testid="tax-mapping-row"][data-slot="STANDARD_20/purchase"]');
  const option = row.locator('option', { hasText: /^34552 / });
  await row.locator('select').selectOption((await option.getAttribute('value')) ?? '');
  await expect(row.getByTestId('tax-mapping-state')).toContainText('Approuvé');
  await page.getByTestId('btn-logout').click();
  await page.waitForURL((u) => u.pathname === '/');
});

test('accountant uploads, proposes, acknowledges and requests approval', async ({ page }) => {
  const log = recordApiTraffic(page, 'phase5-accountant');
  await loginThroughKeycloak(page);
  await page.getByRole('link', { name: COMPANY }).click();
  await page.getByTestId('input-upload').setInputFiles({ name: 'facture-souss.pdf', mimeType: 'application/pdf', buffer: INVOICE });
  await expect(page.getByTestId('msg-ok')).toContainText('facture-souss.pdf lue', { timeout: 120_000 });
  await page.getByTestId('doc-row').filter({ hasText: 'facture-souss.pdf' }).getByRole('button', { name: "Proposer l'écriture" }).click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'Écriture proposée' })).toBeVisible();

  // Every open review issue is acknowledged with a reason, by a person. Wait for the file screen
  // to show the issue raised by the proposal before looking for the buttons.
  await expect(page.locator('[data-testid="issue-row"][data-code="ACCOUNT_LOW_CONFIDENCE"]')).toBeVisible();
  const ackButtons = page.locator('[data-testid^="btn-ack-"]');
  while ((await ackButtons.count()) > 0) {
    const id = ((await ackButtons.first().getAttribute('data-testid')) ?? '').replace('btn-ack-', '');
    await ackButtons.first().click();
    await page.getByTestId(`input-issue-${id}`).fill('Compte de charge vérifié sur la facture.');
    await page.getByTestId(`btn-issue-submit-${id}`).click();
    await expect(page.getByTestId(`btn-ack-${id}`)).toHaveCount(0);
  }
  await page.getByTestId('btn-request-approval').click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'Validation demandée' })).toBeVisible();
  await expect.poll(() => log.some((l) => /\/approvals -> 201/.test(l))).toBe(true);
  await page.getByTestId('btn-logout').click();
  await page.waitForURL((u) => u.pathname === '/');
});

test('expert approves after a real MFA step-up, then exports', async ({ page }) => {
  test.setTimeout(10 * 60_000);
  const log = recordApiTraffic(page, 'phase5-expert');
  await loginThroughKeycloak(page, { username: EXPERT });

  await page.getByRole('link', { name: 'Validations' }).click();
  await page.getByRole('link', { name: COMPANY }).click();
  await expect(page.getByTestId('approval-page')).toContainText(COMPANY);
  await page.screenshot({ path: `${SHOTS}/01-approval-summary.png`, fullPage: true });

  // Let the MFA login age past 5 minutes, then try to approve: the browser must re-authenticate.
  console.log(`[phase5-expert] waiting ${STEP_UP_WAIT_MS / 1000}s so the MFA login is older than 5 minutes`);
  await page.waitForTimeout(STEP_UP_WAIT_MS);
  await page.getByRole('button', { name: 'Valider le dossier' }).click();
  await page.waitForURL(/\/realms\/avenel\/(protocol\/openid-connect\/auth|login-actions)/);
  const authUrl = page.url();
  console.log(`[phase5-expert] step-up redirect: prompt=login ${authUrl.includes('prompt=login')} max_age=300 ${authUrl.includes('max_age=300')}`);
  if (await page.locator('#username').isVisible()) await page.locator('#username').fill(EXPERT);
  const realm = JSON.parse(readFileSync('docker/keycloak/realm-export-test.json', 'utf8')) as { users: { username: string; credentials: { type: string; value?: string }[] }[] };
  const pwd = realm.users.find((u) => u.username === EXPERT)!.credentials.find((c) => c.type === 'password')!.value!;
  await page.locator('#password').fill(pwd);
  await page.locator('#kc-login').click();
  await expect(page.locator('#otp')).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/02-step-up-otp.png`, fullPage: true });
  await page.locator('#otp').fill(await currentTotp(EXPERT));
  await page.locator('#kc-login').click();
  await page.waitForURL(/\/approvals\/[0-9a-f-]+$/);

  // Back on the approval page with a fresh MFA login: the decision goes through
  await page.getByRole('button', { name: 'Valider le dossier' }).click();
  await expect(page.getByTestId('msg-ok')).toContainText('Dossier validé');
  await expect.poll(() => log.some((l) => /:decide -> 200/.test(l))).toBe(true);

  // Export: Sage 100 CSV, then download the file through the API
  await page.getByRole('button', { name: /Générer l'export/ }).click();
  await expect(page.getByTestId('msg-ok')).toContainText('Export prêt');
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Télécharger les écritures' }).click()]);
  const path = await download.path();
  const content = readFileSync(path!, 'latin1');
  console.log(`[phase5-expert] downloaded ${download.suggestedFilename()} (${content.length} bytes)\n${content.trim()}`);
  expect(content).toContain('12000,00');
  await page.screenshot({ path: `${SHOTS}/03-export-ready.png`, fullPage: true });
  for (const p of [':decide -> 200', '/exports -> 201', '/file -> 200']) {
    await expect.poll(() => log.some((l) => l.includes(p)), { message: `expected API call: ${p}` }).toBe(true);
  }
});
