// Phase 3 through the browser, real stack: a registered professional approves the VAT account,
// a scanned invoice is read, an entry is proposed from it, and reviewed with its evidence boxes.
// No interception (Part K 26); API traffic logged.
import { mkdirSync, readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { API_ORIGIN, EXPERT, loginThroughKeycloak, recordApiTraffic } from './stack';

const SHOTS = 'docs/reports/phase-3';
mkdirSync(SHOTS, { recursive: true });
// A trailing PDF comment makes the bytes unique per run, so the upload is not refused as a resubmission
// on a stack that already holds this file (D-18). Content and OCR result are unchanged.
const SCANNED = Buffer.concat([readFileSync('e2e/assets/invoice-scanned.pdf'), Buffer.from(`
%run-${Date.now()}
`)]);
// A new client company per run: tax-account approvals are kept for good, so a reused company would
// already show the 20 % account as approved (D-18). Created through the API with the expert's own token.
const FILE = `Atlas E2E ${Date.now()} SARL`;

test('expert approves VAT account, proposes an entry from a read invoice, reviews it', async ({ page, request }) => {
  test.setTimeout(420_000); // the AI job may take minutes before the agents hand off
  const log = recordApiTraffic(page, 'phase3-expert');
  let bearer = '';
  page.on('request', (r) => {
    const a = r.headers()['authorization'];
    if (r.url().startsWith(API_ORIGIN) && a) bearer = a;
  });
  await loginThroughKeycloak(page, { username: EXPERT });

  // The token proves MFA (amr) — required by the API for members with a professional registration.
  await expect.poll(() => bearer).toMatch(/^Bearer ey/);
  const claims = JSON.parse(Buffer.from(bearer.split('.')[1], 'base64url').toString()) as { amr?: string[] };
  console.log(`[phase3-expert] token amr=${JSON.stringify(claims.amr)}`);
  expect(claims.amr).toContain('otp');

  const auth = { Authorization: bearer };
  const client = await request.post(`${API_ORIGIN}/v1/client-entities`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-client-${FILE}` }, data: { legal_name: FILE, ice: `99${String(Date.now()).slice(-13)}` }, // one client per ICE per firm
  });
  expect(client.status()).toBe(201);
  const clientId = ((await client.json()) as { id: string }).id;
  const period = await request.post(`${API_ORIGIN}/v1/client-entities/${clientId}/periods`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-period-${FILE}` },
    data: { period_code: '2026-09', starts_on: '2026-09-01', ends_on: '2026-09-30', fiscal_year_end: '2026-12-31' },
  });
  expect(period.status()).toBe(201);
  const periodId = ((await period.json()) as { id: string }).id;
  const wr = await request.post(`${API_ORIGIN}/v1/work-requests`, {
    headers: { ...auth, 'Idempotency-Key': `e2e-wr-${FILE}` }, data: { client_entity_id: clientId, accounting_period_id: periodId },
  });
  expect(wr.status(), await wr.text()).toBe(201);
  // No page reload: the session token lives in memory, a reload would log the expert out.

  // 1. Client page: chart, then approve the account for 20 % purchases
  await page.getByRole('link', { name: 'Clients' }).click();
  await page.getByRole('link', { name: FILE }).click();
  await page.getByTestId('btn-seed-cgnc').click();
  await expect(page.getByTestId('chart-count')).toBeVisible();
  const row = page.locator('[data-testid="tax-mapping-row"][data-slot="STANDARD_20/purchase"]');
  await expect(row.getByTestId('tax-mapping-state')).toHaveText('À choisir');
  const option = row.locator('option', { hasText: /^34552 / });
  await row.locator('select').selectOption(await option.getAttribute('value') ?? '');
  await expect(row.getByTestId('tax-mapping-state')).toContainText('Approuvé par CI Expert');
  await row.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOTS}/01-tax-mapping-approved.png`, fullPage: true });

  // 2. Monthly file: upload and read the scanned invoice, then propose the entry
  await page.getByRole('link', { name: 'File de travail' }).click();
  await page.getByRole('link', { name: FILE }).click();
  await page.getByTestId('input-upload').setInputFiles({ name: 'facture-atlas.pdf', mimeType: 'application/pdf', buffer: SCANNED });
  await expect(page.getByTestId('msg-ok')).toContainText('facture-atlas.pdf lue', { timeout: 120_000 });
  // Phase 8a: once the invoice is read, the bookkeeping agent proposes the entry on its own (no click).
  // A click afterwards must not create a second entry: the API answers 409 and the page says so.
  const docRow = page.getByTestId('doc-row').filter({ hasText: 'facture-atlas.pdf' });
  const wrIdAgent = page.url().split('/files/')[1].split('/')[0];
  await expect
    .poll(async () => {
      const r = await request.get(`${API_ORIGIN}/v1/work-requests/${wrIdAgent}/agent-tasks`, { headers: { Authorization: bearer } });
      const items = ((await r.json()) as { items: { agent: string; outcome: string }[] }).items;
      // After the reading, the AI help for empty fields runs in its own job (it can take minutes on the
      // hosted provider); the document agent hands off after it.
      return items.map((t) => `${t.agent}:${t.outcome}`).slice(-3);
    }, { timeout: 300_000, intervals: [3_000] }) // not 5 s: uvicorn closes idle keep-alive connections at 5 s
    .toEqual(['document:handed_off', 'bookkeeping:done', 'orchestrator:ready_for_review']);
  console.log(`[phase3-expert] agent chain reached the API for ${wrIdAgent}`);
  await docRow.getByRole('button', { name: "Proposer l'écriture" }).click();
  await expect(page.getByTestId('msg-ok').filter({ hasText: 'Écriture déjà proposée (agent comptable)' })).toBeVisible();

  // 3. Review: balanced entry, VAT line, evidence box on the source page
  await page.getByTestId('link-review').click();
  await expect(page.getByTestId('review-screen')).toBeVisible();
  await expect(page.getByTestId('balance-indicator')).not.toContainText('Déséquilibré');
  await expect(page.getByTestId('review-screen')).toContainText('34552');
  await expect(page.getByTestId('review-screen')).toContainText('4411');
  const img = page.getByTestId('review-page-image');
  await expect(img).toBeVisible();
  await expect.poll(() => img.evaluate((el) => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth > 0)).toBe(true);
  await page.getByTestId('proposal-line-row-1').click();
  await expect(page.getByTestId('evidence-bbox-overlay')).toBeVisible();
  await page.waitForTimeout(400); // 160 ms move (Part E.5)

  // The box must sit on line 1's evidence bbox, measured against the page image itself
  const wrIdForBox = page.url().split('/files/')[1].split('/')[0];
  const firstProposal = ((await (await request.get(`${API_ORIGIN}/v1/work-requests/${wrIdForBox}/proposals`, { headers: { Authorization: bearer } })).json()) as {
    lines: { line_no: number; evidence_refs: { bbox?: number[] }[] }[];
  }[])[0];
  const want = firstProposal.lines.find((l) => l.line_no === 1)!.evidence_refs.find((e) => Array.isArray(e.bbox))!.bbox!;
  const ib = (await img.boundingBox())!;
  const ob = (await page.getByTestId('evidence-bbox-overlay').boundingBox())!;
  const drawn = [(ob.x - ib.x) / ib.width, (ob.y - ib.y) / ib.height, (ob.x + ob.width - ib.x) / ib.width, (ob.y + ob.height - ib.y) / ib.height];
  console.log(`[phase3-expert] line 1 evidence api=${JSON.stringify(want)} drawn=${JSON.stringify(drawn.map((v) => +v.toFixed(3)))}`);
  drawn.forEach((v, i) => expect(Math.abs(v - want[i])).toBeLessThan(0.01));
  await page.screenshot({ path: `${SHOTS}/02-review-entry-evidence.png`, fullPage: true });

  // Through the API with the expert's own token: the entry balances and every line has evidence
  const wrId = page.url().split('/files/')[1].split('/')[0];
  const props = (await (await request.get(`${API_ORIGIN}/v1/work-requests/${wrId}/proposals`, { headers: { Authorization: bearer } })).json()) as {
    lines: { debit_mad: number; credit_mad: number; evidence_refs: { bbox?: number[] }[] }[];
  }[];
  const lines = props[0].lines;
  const sum = (k: 'debit_mad' | 'credit_mad') => Math.round(lines.reduce((s, l) => s + Number(l[k] || 0), 0) * 100) / 100;
  console.log(`[phase3-expert] proposal lines=${lines.length} debit=${sum('debit_mad')} credit=${sum('credit_mad')}`);
  expect(sum('debit_mad')).toBe(12000);
  expect(sum('credit_mad')).toBe(12000);
  for (const l of lines) expect(l.evidence_refs.some((e) => Array.isArray(e.bbox))).toBe(true);

  for (const p of ['PUT http://localhost:8000/v1/client-entities/', '/proposals -> 200']) {
    await expect.poll(() => log.some((l) => l.includes(p) && !/-> [45]\d\d/.test(l)), { message: `expected API call: ${p}` }).toBe(true);
  }
  // The click after the agent proposed is refused (one active entry per document), not a second entry.
  expect(log.some((l) => l.includes(':generate-proposal -> 409'))).toBe(true);
});
