// Phase 2 through the browser, real stack: upload → ClamAV → page render → local OCR → extraction
// → document viewer with field boxes → correction. No interception (Part K 26); API traffic logged.
import { mkdirSync, readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import { API_ORIGIN, CLIENT_USER, loginThroughKeycloak, recordApiTraffic } from './stack';

const SHOTS = 'docs/reports/phase-2';
mkdirSync(SHOTS, { recursive: true });
test.describe.configure({ mode: 'serial' });

// Synthetic test invoice rendered to an image-only PDF (no text layer): OCR must read it.
const SCANNED = readFileSync('e2e/assets/invoice-scanned.pdf');
// EICAR standard antivirus test string (harmless by design), at offset 0 as the standard requires.
const EICAR = Buffer.from('X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*');
const OUT_OF_SCOPE_FILE = 'Riad Menara SARL'; // the client user is scoped to Atlas only (scripts/e2e_seed.json)

function bearerOf(page: Page): () => string {
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  return () => bearer;
}

test('accountant uploads a scanned invoice, it is read, reviewed and corrected', async ({ page, request }) => {
  const log = recordApiTraffic(page, 'phase2-accountant');
  const bearer = bearerOf(page);
  await loginThroughKeycloak(page);

  await page.getByRole('link', { name: OUT_OF_SCOPE_FILE }).click();
  await expect(page.getByTestId('file-title')).toHaveText(OUT_OF_SCOPE_FILE);

  // Upload: init (SHA-256 computed in the browser) → content → complete-upload (scan, render, OCR)
  await page.getByTestId('input-upload').setInputFiles({ name: 'facture-scannee.pdf', mimeType: 'application/pdf', buffer: SCANNED });
  await expect(page.getByTestId('msg-ok')).toContainText('facture-scannee.pdf lue', { timeout: 120_000 });
  const row = page.getByTestId('doc-row').filter({ hasText: 'facture-scannee.pdf' });
  await expect(row).toContainText("Facture d'achat");
  await page.screenshot({ path: `${SHOTS}/01-file-upload-read.png`, fullPage: true });

  // Review: page image from the API, field values read by OCR, field box on focus
  await row.getByRole('link').click();
  // The real page image (an <img> fed by GET /pages/1/image), fully decoded
  const img = page.getByTestId('document-canvas');
  await expect(img).toBeVisible();
  await expect.poll(() => img.evaluate((el) => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth > 0)).toBe(true);
  await expect(page.getByTestId('document-page-missing')).toHaveCount(0);
  await expect(page.getByTestId('field-input-invoice_number')).toHaveValue('FAC-2026-0412');
  await expect(page.getByTestId('field-input-supplier_ice')).toHaveValue('001234567890123');

  // Focus Total TTC: after the 160 ms move, the box must sit on the API's bbox for that field
  const reviewDocId = page.url().split('/documents/')[1];
  const exBefore = await request.get(`${API_ORIGIN}/v1/documents/${reviewDocId}/extraction`, { headers: { Authorization: bearer() } });
  const ttcBox = ((await exBefore.json()) as { fields: Record<string, { bbox: number[] }> }).fields.total_ttc.bbox;
  await page.getByTestId('field-input-total_ttc').focus();
  await page.waitForTimeout(400);
  const imgBox = (await img.boundingBox())!;
  const ovBox = (await page.getByTestId('bbox-overlay').boundingBox())!;
  const rel = [
    (ovBox.x - imgBox.x) / imgBox.width,
    (ovBox.y - imgBox.y) / imgBox.height,
    (ovBox.x + ovBox.width - imgBox.x) / imgBox.width,
    (ovBox.y + ovBox.height - imgBox.y) / imgBox.height,
  ];
  console.log(`[phase2-accountant] total_ttc bbox api=${JSON.stringify(ttcBox)} drawn=${JSON.stringify(rel.map((v) => +v.toFixed(3)))}`);
  rel.forEach((v, i) => expect(Math.abs(v - ttcBox[i])).toBeLessThan(0.01));
  await page.getByTestId('bbox-overlay').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOTS}/02-review-bbox.png`, fullPage: true });

  // Correction, persisted by the API (evidence record written server side)
  await page.getByTestId('field-input-supplier_name').fill('Société Atlas Fournitures SARL');
  await page.getByTestId('save-corrections-btn').click();
  await expect(page.getByTestId('save-success-banner')).toBeVisible();
  const docId = page.url().split('/documents/')[1];
  const ex = await request.get(`${API_ORIGIN}/v1/documents/${docId}/extraction`, { headers: { Authorization: bearer() } });
  const fields = ((await ex.json()) as { fields: Record<string, { value: unknown }> }).fields;
  expect(fields.supplier_name.value).toBe('Société Atlas Fournitures SARL');
  process.env.E2E_PHASE2_DOC = docId;

  for (const p of [
    '/uploads -> 201',
    `/documents/${docId}/content -> 200`,
    `/documents/${docId}:complete-upload -> 200`,
    `/documents/${docId}/pages/1/image -> 200`,
    `/documents/${docId}/extraction -> 200`,
    `PATCH http://localhost:8000/v1/documents/${docId}/extraction -> 200`,
  ]) {
    await expect.poll(() => log.some((l) => l.includes(p)), { message: `expected API call: ${p}` }).toBe(true);
  }

  // Malware: real ClamAV detects EICAR → quarantined, blocking issue shown, no review link
  await page.getByRole('link', { name: 'Dossier mensuel' }).click();
  await page.getByTestId('input-upload').setInputFiles({ name: 'eicar.pdf', mimeType: 'application/pdf', buffer: EICAR });
  await expect(page.getByTestId('msg-error')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId('doc-row').filter({ hasText: 'eicar.pdf' })).toHaveAttribute('data-status', 'quarantined');
  await expect(page.getByTestId('issue-strip')).toContainText('bloquante');
  await expect(page.locator('[data-testid="issue-row"][data-code="DOC_MALWARE"]')).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/03-eicar-quarantined.png`, fullPage: true });
  await expect.poll(() => log.some((l) => /:complete-upload -> 422/.test(l))).toBe(true);

  await page.getByTestId('btn-logout').click();
  await page.waitForURL((u) => u.pathname === '/');
});

test('client user cannot open a document of another company', async ({ page, request }) => {
  recordApiTraffic(page, 'phase2-client-user');
  const bearer = bearerOf(page);
  await loginThroughKeycloak(page, { username: CLIENT_USER });
  const docId = process.env.E2E_PHASE2_DOC;
  expect(docId, 'document id from the accountant test').toBeTruthy();
  await page.waitForTimeout(300);
  for (const path of [`/v1/documents/${docId}`, `/v1/documents/${docId}/extraction`, `/v1/documents/${docId}/pages/1/image`]) {
    const r = await request.get(`${API_ORIGIN}${path}`, { headers: { Authorization: bearer() } });
    console.log(`[phase2-client-user] direct GET ${API_ORIGIN}${path} -> ${r.status()}`);
    expect(r.status()).toBe(404);
  }
  await page.evaluate((path) => {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }, `/documents/${docId}`);
  await expect(page.getByText('Pièce introuvable.')).toBeVisible();
});
