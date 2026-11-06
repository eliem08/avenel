// Real stack: browser → Keycloak (password + TOTP) → Vite app (nginx) → FastAPI → PostgreSQL.
// Nothing is intercepted or stubbed (Part K 26). API traffic is logged for the phase report.
import { expect, test } from '@playwright/test';
import { API_ORIGIN, SHOTS, loginThroughKeycloak, recordApiTraffic, seed } from './stack';

test('accountant logs in with TOTP, sees seeded queue from the API, logs out', async ({ page, request }) => {
  const apiLines = recordApiTraffic(page, 'login-queue');
  let bearer = '';
  page.on('request', (req) => {
    if (req.url() === `${API_ORIGIN}/v1/work-requests`) bearer = req.headers()['authorization'] ?? '';
  });

  // 1. "/" is the AVENEL login; protected routes redirect there.
  await page.goto('/queue');
  await expect(page).toHaveURL(/\/$/);

  // 2. Keycloak password + TOTP from the test realm secret.
  await loginThroughKeycloak(page, { screenshots: true });

  // 3. Queue shows the seeded monthly files, loaded from GET /v1/work-requests.
  const rows = page.getByTestId('queue-row');
  await expect(rows).toHaveCount(seed.clients.length);
  for (const c of seed.clients) await expect(page.getByTestId('queue-table')).toContainText(c.legal_name);
  await expect(page.getByTestId('queue-table')).toContainText('À valider');
  await expect(page.getByTestId('firm-switcher')).toHaveAttribute('data-tenant-id', seed.tenant_id);
  await page.screenshot({ path: `${SHOTS}/03-queue.png`, fullPage: true });

  await expect.poll(() => apiLines.some((l) => l.includes('GET http://localhost:8000/v1/work-requests -> 200 bearer_jwt=true'))).toBe(true);
  await expect.poll(() => apiLines.some((l) => l.includes('GET http://localhost:8000/v1/client-entities -> 200 bearer_jwt=true'))).toBe(true);

  // 4. Through the API directly, with the browser's own token: session tenant equals the seed tenant.
  expect(bearer).toMatch(/^Bearer ey/);
  const me = await request.get(`${API_ORIGIN}/v1/me`, { headers: { Authorization: bearer } });
  expect(me.status()).toBe(200);
  const body = (await me.json()) as { tenant_id: string; role: string; email: string };
  console.log(`[login-queue] direct GET ${API_ORIGIN}/v1/me -> ${me.status()} tenant_id=${body.tenant_id} role=${body.role}`);
  expect(body.tenant_id).toBe(seed.tenant_id);
  expect(body.email).toBe(seed.user_email);

  // 5. Same endpoint without a token, or with a forged subject header, is refused.
  expect((await request.get(`${API_ORIGIN}/v1/me`)).status()).toBe(401);
  expect((await request.get(`${API_ORIGIN}/v1/me`, { headers: { 'X-Identity-Subject': seed.user_subject } })).status()).toBe(401);

  // 6. Tokens are not in Web Storage.
  const storage = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }));
  expect(storage).toEqual({ local: 0, session: 0 });

  // 7. Logout ends the Keycloak session and returns to "/".
  await page.getByTestId('btn-logout').click();
  await page.waitForURL((u) => u.pathname === '/' && u.port === '5173');
  await expect(page.getByTestId('btn-login')).toBeVisible();
  await page.goto('/queue');
  await expect(page).toHaveURL(/\/$/);
});
