// Self-tests: each guard catches a planted violation and passes clean input.
import { describe, expect, it } from 'vitest';
import { checkBundle, checkPySource, checkTsSource } from './no_test_code_in_prod.mjs';
import { checkE2e } from './no_e2e_interception.mjs';
import { checkText } from './no_legacy_terms.mjs';

describe('Part K 25 — no test code in production', () => {
  it('flags imports from tests/ or fixtures/', () => {
    expect(checkTsSource('src/a.ts', "import x from '../tests/data';")).toHaveLength(1);
    expect(checkTsSource('src/a.ts', "import { y } from '@/fixtures/queue';")).toHaveLength(1);
  });
  it('flags mock/fixture/fake identifiers and modules', () => {
    expect(checkTsSource('src/a.ts', 'export const mockQueueItems = [];')).toHaveLength(1);
    expect(checkTsSource('src/a.ts', 'function fakeLogin() {}')).toHaveLength(1);
    expect(checkTsSource('src/mockData.ts', 'export {}')).toHaveLength(1);
  });
  it('flags Python imports from tests', () => {
    expect(checkPySource('avenel/x.py', 'from tests.fixtures.documents_300 import A')).toHaveLength(1);
  });
  it('flags bundles containing the names', () => {
    expect(checkBundle('dist/a.js', 'var mockQueueItems=[]')).toHaveLength(1);
  });
  it('passes clean code', () => {
    expect(checkTsSource('src/a.ts', "import { useApi } from '@/api/useApi';\nconst rows = [];")).toEqual([]);
    expect(checkPySource('avenel/x.py', 'from avenel.tenancy import auth')).toEqual([]);
  });
});

describe('Part K 26 — no e2e network interception', () => {
  it('flags page.route and route.fulfill', () => {
    expect(checkE2e('e2e/a.ts', "await page.route('**/v1/**', (r) => r.fulfill({ body: '{}' }));").length).toBeGreaterThan(0);
    expect(checkE2e('e2e/a.ts', 'await context.routeFromHAR("x.har");').length).toBeGreaterThan(0);
    expect(checkE2e('e2e/a.ts', 'await context.setOffline(true);').length).toBeGreaterThan(0);
  });
  it('allows observing requests', () => {
    expect(checkE2e('e2e/a.ts', "page.on('request', (r) => log.push(r.url()));")).toEqual([]);
  });
});

describe('Part K 27 — no previous-product terms', () => {
  it('flags each term case-insensitively', () => {
    for (const t of ['preclear', 'Douane', 'DOUANIER', 'portnet', 'badr', 'code  SH', 'Transitaire', 'riskscoring', 'FiscAI']) {
      expect(checkText('x', `a ${t} b`)).toHaveLength(1);
    }
  });
  it('passes AVENEL copy', () => {
    expect(checkText('x', 'Dossiers mensuels · À valider')).toEqual([]);
  });
});
