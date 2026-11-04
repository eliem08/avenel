// Part K 27: no terms from the previous product in source or bundle.
import { fileURLToPath } from 'node:url';
import { read, report, trackedFiles, walk } from './lib.mjs';

export const TERMS = ['PreClear', 'douane', 'douanier', 'PortNet', 'BADR', 'code SH', 'transitaire', 'riskScoring', 'fiscai'];
const RX = new RegExp(TERMS.map((t) => t.replace(/ /g, '\\s+')).join('|'), 'i');

// Files that must name the terms to do their job. Nothing else is excluded.
const EXCLUDED = new Set([
  'scripts/guards/no_legacy_terms.mjs',
  'scripts/guards/guards.test.mjs',
  'TESTS_REMOVED.md',
]);
// Historical reports and plans describe the split and are not source.
const EXCLUDED_DIRS = ['docs/'];
const BINARY = /\.(woff2?|png|jpe?g|gif|ico|pdf|zip|xlsx)$/i;

export function checkText(path, text) {
  const v = [];
  text.split(/\r?\n/).forEach((line, i) => {
    const m = line.match(RX);
    if (m && !isAllowed(path, line)) v.push(`${path}:${i + 1}: '${m[0]}'`);
  });
  return v;
}

// Human-approved (Phase 5c-1, Part K 27): AVENEL backend lines where the word is the
// correct Moroccan accounting/legal term. Matched by file AND exact text fragment, so
// any new occurrence, even in these files, still fails.
export const ALLOWED_LINES = [
  ['avenel/compliance/dpa.py', "numéros d'identification fiscal et douanier (ICE, IF, RC)"],
  ['avenel/extraction/classifier.py', '["douane", "déclaration unique de marchandise", "dum", "جمارك"]'],
  ['tests/issues/test_issues.py', 'Écart de date justifié par le bon de réception du transitaire'],
  // Part K 27 itself lists the forbidden terms.
  ['ARCHITECTURE.md', 'Tracked source and the built bundle must not contain `PreClear`'],
];

function isAllowed(path, line) {
  return ALLOWED_LINES.some(([f, frag]) => f === path && line.includes(frag));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const v = [];
  for (const f of trackedFiles(['.'])) {
    if (EXCLUDED.has(f) || EXCLUDED_DIRS.some((d) => f.startsWith(d)) || BINARY.test(f) || f === 'package-lock.json') continue;
    v.push(...checkText(f, read(f)));
  }
  const dist = walk('dist').filter((f) => /\.(js|css|html)$/.test(f));
  if (dist.length === 0) v.push('dist/ is empty: run `npm run build` first');
  for (const f of dist) v.push(...checkText(f, read(f)));
  report('no_legacy_terms', v);
}
