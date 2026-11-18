import { defineConfig, devices } from '@playwright/test';

// Runs against the docker-compose stack only (`make e2e` starts it and checks health first).
// No webServer: Playwright never starts a static preview, and no request is intercepted (Part K 26).
export default defineConfig({
  testDir: './e2e',
  // The live-demo setup adds a client company; in the suite it ran first and broke the exact client and
  // queue counts of login-queue and phase 1 (CI, 15-18 Nov 2026). Run it with playwright.demo.config.ts.
  testIgnore: ['**/demo-setup.spec.ts'],
  fullyParallel: false,
  workers: 1,
  // A second login may wait up to 30 s for a fresh TOTP window (e2e/stack.ts).
  timeout: 90_000,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    locale: 'fr-FR',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
