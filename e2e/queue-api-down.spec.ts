// Real stack with the API container stopped by `make e2e` before this file runs (tag @api-down).
// Keycloak is up, so login is real; the Queue must show its error state.
import { expect, test } from '@playwright/test';
import { SHOTS, loginThroughKeycloak, recordApiTraffic } from './stack';

test('@api-down queue shows the error state when the API is down', async ({ page }) => {
  const apiLines = recordApiTraffic(page, 'api-down');
  await loginThroughKeycloak(page);
  await expect(page.getByTestId('state-error')).toContainText("Les dossiers n'ont pas pu être chargés.");
  await page.screenshot({ path: `${SHOTS}/04-queue-api-down.png`, fullPage: true });
  await expect.poll(() => apiLines.some((l) => l.includes('/v1/work-requests -> FAILED'))).toBe(true);
});
