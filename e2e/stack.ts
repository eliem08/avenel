// Helpers for e2e tests against the docker-compose stack. Observation only: no request is modified.
import { readFileSync, mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import { expect, type Page } from '@playwright/test';
import { Secret, TOTP } from 'otpauth';

interface RealmCredential { type: string; value?: string; secretData?: string }
const realm = JSON.parse(readFileSync('docker/keycloak/realm-export-test.json', 'utf8')) as {
  users: { username: string; credentials: RealmCredential[] }[];
};

export const ACCOUNTANT = 'ci-accountant@test.internal';
export const CLIENT_USER = 'ci-client@test.internal';

function credentials(username: string): { password: string; otpSecret: string } {
  const u = realm.users.find((x) => x.username === username);
  if (!u) throw new Error(`test realm has no user ${username}`);
  const password = u.credentials.find((c) => c.type === 'password')?.value ?? '';
  const otp = JSON.parse(u.credentials.find((c) => c.type === 'otp')?.secretData ?? '{}') as { value?: string };
  return { password, otpSecret: otp.value ?? '' };
}

export const seed = JSON.parse(readFileSync('scripts/e2e_seed.json', 'utf8')) as {
  tenant_id: string;
  user_subject: string;
  user_email: string;
  clients: { legal_name: string; status: string }[];
  client_user: { subject: string; email: string; scoped_to: string };
};

export const API_ORIGIN = process.env.E2E_API_ORIGIN ?? 'http://localhost:8000';
export const SHOTS = 'docs/reports/phase-5c-1';
export const API_LOG = `${SHOTS}/e2e-browser-api-requests.log`;
mkdirSync(SHOTS, { recursive: true });

/** Records every browser request to the API with its response status (page.on, no interception). */
export function recordApiTraffic(page: Page, label: string): string[] {
  const lines: string[] = [];
  page.on('response', async (res) => {
    const req = res.request();
    if (!req.url().startsWith(API_ORIGIN) || req.method() === 'OPTIONS') return;
    const hasBearer = (req.headers()['authorization'] ?? '').startsWith('Bearer ey');
    const detail = res.status() >= 400 ? ` body=${(await res.text().catch(() => '')).slice(0, 300)}` : '';
    const line = `${new Date().toISOString()} [${label}] ${req.method()} ${req.url()} -> ${res.status()} bearer_jwt=${hasBearer}${detail}`;
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

// Keycloak rejects a one-time code that was already used, so two logins inside the same
// 30 s window fail. Spec files run in separate processes, and Playwright empties test-results/
// at the start of every run, so the last used step is kept in .e2e-state/ instead.
// One file per user: replay protection is per OTP credential.
const lastStepFile = (username: string) => `.e2e-state/last-totp-step-${username.replace(/[^a-z0-9]/gi, '_')}`;

/** TOTP code from the test realm secret: never reuses a time step, avoids the last 3 s of a window. */
export async function currentTotp(username: string = ACCOUNTANT): Promise<string> {
  const { otpSecret } = credentials(username);
  const LAST_STEP_FILE = lastStepFile(username);
  // Keycloak stores the raw secret string; the authenticator key is its bytes (not a base32 decode).
  const totp = new TOTP({ secret: Secret.fromLatin1(otpSecret), digits: 6, period: 30, algorithm: 'SHA1' });
  let last = -1;
  try {
    last = Number(readFileSync(LAST_STEP_FILE, 'utf8'));
  } catch {
    /* first login of the run */
  }
  for (;;) {
    const now = Date.now() / 1000;
    const step = Math.floor(now / 30);
    const remaining = 30 - (now % 30);
    if (step > last && remaining >= 3) {
      mkdirSync('.e2e-state', { recursive: true });
      writeFileSync(LAST_STEP_FILE, String(step));
      return totp.generate({ timestamp: step * 30 * 1000 });
    }
    await new Promise((r) => setTimeout(r, remaining * 1000 + 200));
  }
}

/** Full Keycloak login: "/" → Keycloak password → Keycloak OTP → app. */
export async function loginThroughKeycloak(
  page: Page,
  opts: { screenshots?: boolean; username?: string } = {},
) {
  const username = opts.username ?? ACCOUNTANT;
  const { password } = credentials(username);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  if (opts.screenshots) await page.screenshot({ path: `${SHOTS}/01-login.png`, fullPage: true });
  await page.getByTestId('btn-login').click();

  await page.waitForURL(/\/realms\/avenel\/protocol\/openid-connect\/auth|login-actions/);
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.locator('#kc-login').click();

  await expect(page.locator('#otp')).toBeVisible();
  if (opts.screenshots) await page.screenshot({ path: `${SHOTS}/02-mfa-prompt.png`, fullPage: true });
  await page.locator('#otp').fill(await currentTotp(username));
  await page.locator('#kc-login').click();
  await page.waitForURL('**/queue');
}
