// Phase 8d through the browser, real stack: the firm manager cancels a monthly file with a reason.
// The file shows as cancelled, takes no more documents, keeps its history, and the period gets a new file.
// No interception (Part K 26); API traffic logged.
import { mkdirSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { API_ORIGIN, MANAGER, loginThroughKeycloak, recordApiTraffic } from './stack';

const SHOTS = 'docs/reports/phase-8d';
mkdirSync(SHOTS, { recursive: true });
const NAME = `Annulation E2E ${Date.now()} SARL`;
const REASON = 'Le client a confié sa comptabilité à un autre cabinet.';

test('manager cancels a monthly file with a reason, and the period gets a new file', async ({ page, request }) => {
  const log = recordApiTraffic(page, 'phase8d-manager');
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  await loginThroughKeycloak(page, { username: MANAGER });
  await expect.poll(() => bearer).toMatch(/^Bearer ey/);
  const auth = { Authorization: bearer };

  // A file of its own, created through the API with the manager's token.
  const c = await request.post(`${API_ORIGIN}/v1/client-entities`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-8d-client-${NAME}` },
    data: { legal_name: NAME, ice: `97${String(Date.now()).slice(-13)}` },
  });
  expect(c.status(), await c.text()).toBe(201);
  const clientId = ((await c.json()) as { id: string }).id;
  const p = await request.post(`${API_ORIGIN}/v1/client-entities/${clientId}/periods`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-8d-period-${NAME}` },
    data: { period_code: '2026-10', starts_on: '2026-10-01', ends_on: '2026-10-31', fiscal_year_end: '2026-12-31' },
  });
  expect(p.status(), await p.text()).toBe(201);
  const periodId = ((await p.json()) as { id: string }).id;
  const w = await request.post(`${API_ORIGIN}/v1/work-requests`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-8d-wr-${NAME}` },
    data: { client_entity_id: clientId, accounting_period_id: periodId },
  });
  expect(w.status(), await w.text()).toBe(201);
  const fileId = ((await w.json()) as { id: string }).id;

  // The screen: cancel with a reason. Opened through the app's links (a page load would drop the in-memory session).
  await page.getByRole('link', { name: 'Clients' }).click();
  await page.getByRole('link', { name: 'File de travail' }).click();
  await page.getByRole('link', { name: NAME }).click();
  await expect(page).toHaveURL(new RegExp(`/files/${fileId}$`));
  await expect(page.getByTestId('file-title')).toHaveText(NAME);
  await expect(page.getByTestId('file-status')).toHaveAttribute('data-status', 'draft');
  await page.getByTestId('btn-cancel-file').click();
  await expect(page.getByTestId('btn-cancel-confirm')).toBeDisabled(); // a reason is required
  await page.getByTestId('input-cancel-reason').fill(REASON);
  await page.getByTestId('btn-cancel-confirm').click();

  await expect(page.getByTestId('file-status')).toHaveAttribute('data-status', 'cancelled');
  await expect(page.getByTestId('file-status')).toContainText('Annulé');
  await expect(page.getByTestId('file-closed')).toBeVisible();
  await expect(page.getByTestId('btn-cancel-file')).toHaveCount(0);
  await expect(page.getByTestId('btn-request-approval')).toHaveCount(0);
  await expect(page.locator('input[type="file"]')).toHaveCount(0); // no more uploads
  await expect(page.getByText('Déposez les pièces du mois')).toHaveCount(0);
  await page.getByTestId('status-history').locator('summary').click();
  const last = page.getByTestId('status-change').last();
  await expect(last).toHaveAttribute('data-to', 'cancelled');
  await expect(last).toContainText(REASON);
  await page.screenshot({ path: `${SHOTS}/01-file-cancelled.png`, fullPage: true });

  // Through the API, with the browser's own token.
  await expect.poll(() => log.some((l) => l.includes(`POST ${API_ORIGIN}/v1/work-requests/${fileId}:cancel -> 200`))).toBe(true);
  const hist = await request.get(`${API_ORIGIN}/v1/work-requests/${fileId}/status-history`, { headers: auth });
  const items = ((await hist.json()) as { items: { from_status: string; to_status: string; reason: string | null }[] }).items;
  expect(items.at(-1)).toMatchObject({ from_status: 'draft', to_status: 'cancelled', reason: REASON });
  console.log(`[phase8d-manager] history ${items.map((i) => `${i.from_status}>${i.to_status}`).join(' ')}`);

  const again = await request.post(`${API_ORIGIN}/v1/work-requests/${fileId}:cancel`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-8d-again-${NAME}` }, data: { reason: REASON },
  });
  expect(again.status()).toBe(409);
  const fresh = await request.post(`${API_ORIGIN}/v1/work-requests`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-8d-wr2-${NAME}` },
    data: { client_entity_id: clientId, accounting_period_id: periodId },
  });
  expect(fresh.status(), await fresh.text()).toBe(201);
});
