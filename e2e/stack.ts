// Helpers for e2e tests against the docker-compose stack. Observation only: no request is modified.
import { readFileSync, mkdirSync, appendFileSync } from 'node:fs';
import { expect, type Page } from '@playwright/test';
import { TOTP } from 'otpauth';

interface RealmCredential { type: string; value?: string; secretData?: string }
const realm = JSON.parse(readFileSync('docker/keycloak/realm-export-test.json', 'utf8')) as {
  users: { username: string; credentials: RealmCredential[] }[];
};
const user = realm.users[0];
const password = user.credentials.find((c) => c.type === 'password')?.value ?? '';
const otpSecret = (JSON.parse(user.credentials.find((c) => c.type === 'otp')?.secretData ?? '{}') as { value?: string }).value ?? '';

export const seed = JSON.parse(readFileSync('scripts/e2e_seed.json', 'utf8')) as {
  tenant_id: string;
  user_subject: string;
  user_email: string;
  clients: { legal_name: string; status: string }[];
};

export const API_ORIGIN = process.env.E2E_API_ORIGIN ?? 'http://localhost:8000';
export const SHOTS = 'docs/reports/phase-5c-1';
export const API_LOG = `${SHOTS}/e2e-browser-api-requests.log`;
mkdirSync(SHOTS, { recursive: true });

/** Records every browser request to the API with its response status (page.on, no interception). */
export function recordApiTraffic(page: Page, label: string): string[] {
  const lines: string[] = [];
  page.on('response', (res) => {
    const req = res.request();
    if (!req.url().startsWith(API_ORIGIN)) return;
    const hasBearer = (req.headers()['authorization'] ?? '').startsWith('Bearer ey');
    const line = `${new Date().toISOString()} [${label}] ${req.method()} ${req.url()} -> ${res.status()} bearer_jwt=${hasBearer}`;
    lines.push(line);
    appendFileSync(API_LOG, line + '\n');
    console.log(line);
  });
  page.on('requestfailed', (req) => {
    if (!req.url().startsWith(API_ORIGIN)) return;
    const line = `${new Date().toISOString()} [${label}] ${req.method()} ${req.url()} -> FAILED ${req.failure()?.errorText}`;
    lines.push(line);
    appendFileSync(API_LOG, line + '\n');
    console.log(line);
  });
  return lines;
}

/** Current TOTP code from the test realm secret, avoiding the last 3 s of a window. */
export async function currentTotp(): Promise<string> {
  const totp = new TOTP({ secret: otpSecret, digits: 6, period: 30, algorithm: 'SHA1' });
  const remaining = 30 - (Math.floor(Date.now() / 1000) % 30);
  if (remaining < 3) await new Promise((r) => setTimeout(r, remaining * 1000 + 200));
  return totp.generate();
}

/** Full Keycloak login: "/" → Keycloak password → Keycloak OTP → app. */
export async function loginThroughKeycloak(page: Page, opts: { screenshots?: boolean } = {}) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  if (opts.screenshots) await page.screenshot({ path: `${SHOTS}/01-login.png`, fullPage: true });
  await page.getByTestId('btn-login').click();

  await page.waitForURL(/\/realms\/avenel\/protocol\/openid-connect\/auth|login-actions/);
  await page.locator('#username').fill(user.username);
  await page.locator('#password').fill(password);
  await page.locator('#kc-login').click();

  await expect(page.locator('#otp')).toBeVisible();
  if (opts.screenshots) await page.screenshot({ path: `${SHOTS}/02-mfa-prompt.png`, fullPage: true });
  await page.locator('#otp').fill(await currentTotp());
  await page.locator('#kc-login').click();
  await page.waitForURL('**/queue');
}
