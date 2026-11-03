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
    if (m) v.push(`${path}:${i + 1}: '${m[0]}'`);
  });
  return v;
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
