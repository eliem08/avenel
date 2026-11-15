// Demo setup (local stack): logs in as the expert through Keycloak and creates a fresh client company,
// its September 2026 period and its monthly file, ready for a live upload. Run: npx playwright test e2e/demo-setup.spec.ts
import { expect, test } from '@playwright/test';
import { API_ORIGIN, EXPERT, loginThroughKeycloak } from './stack';

const NAME = `Société Démo ${new Date().toISOString().slice(5, 16).replace('T', ' ')} SARL`;

test('create a demo client ready for a live upload', async ({ page, request }) => {
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  await loginThroughKeycloak(page, { username: EXPERT });
  await expect.poll(() => bearer).toMatch(/^Bearer ey/);
  const auth = { Authorization: bearer };
  const c = await request.post(`${API_ORIGIN}/v1/client-entities`, {
    headers: { ...auth, 'Idempotency-Key': `demo-client-${NAME}` },
    data: { legal_name: NAME, ice: `98${String(Date.now()).slice(-13)}` },
  });
  expect(c.status(), await c.text()).toBe(201);
  const clientId = ((await c.json()) as { id: string }).id;
  const p = await request.post(`${API_ORIGIN}/v1/client-entities/${clientId}/periods`, {
    headers: { ...auth, 'Idempotency-Key': `demo-period-${NAME}` },
    data: { period_code: '2026-09', starts_on: '2026-09-01', ends_on: '2026-09-30', fiscal_year_end: '2026-12-31' },
  });
  expect(p.status(), await p.text()).toBe(201);
  const w = await request.post(`${API_ORIGIN}/v1/work-requests`, {
    headers: { ...auth, 'Idempotency-Key': `demo-wr-${NAME}` },
    data: { client_entity_id: clientId, accounting_period_id: ((await p.json()) as { id: string }).id },
  });
  expect(w.status(), await w.text()).toBe(201);
  console.log(`DEMO CLIENT READY: ${NAME}`);
});
