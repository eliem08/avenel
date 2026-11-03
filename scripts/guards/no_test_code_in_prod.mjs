// Part K 25: production code never imports test code, and nothing named mock*/fixture*/fake* ships.
import { fileURLToPath } from 'node:url';
import { read, report, trackedFiles, walk } from './lib.mjs';

const TEST_FILE = /(\.test\.[cm]?[jt]sx?$|\/test\/|^src\/test\/)/;
const NAME = /\b(mock|fixture|fake)\w*/i;
const TS_IMPORT = /(?:import|export)[^'"]*?from\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)|require\(\s*['"]([^'"]+)['"]\s*\)/g;
const PY_IMPORT = /^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))/gm;

/** Checks one production TS/JS source file. */
export function checkTsSource(path, text) {
  const v = [];
  for (const m of text.matchAll(TS_IMPORT)) {
    const spec = m[1] ?? m[2] ?? m[3];
    if (/(^|\/)(tests?|fixtures?|e2e|__mocks__)(\/|$)/.test(spec) || NAME.test(spec.split('/').pop() ?? '')) {
      v.push(`${path}: imports test code '${spec}'`);
    }
  }
  const code = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  const decl = /\b(?:const|let|var|function|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/g;
  for (const m of code.matchAll(decl)) if (/^(mock|fixture|fake)/i.test(m[1])) v.push(`${path}: declares '${m[1]}'`);
  if (/^(mock|fixture|fake)/i.test(path.split('/').pop() ?? '')) v.push(`${path}: module name`);
  return v;
}

/** Checks one production Python file. */
export function checkPySource(path, text) {
  const v = [];
  for (const m of text.matchAll(PY_IMPORT)) {
    const mod = m[1] ?? m[2];
    if (/^(tests|fixtures)(\.|$)/.test(mod) || /(^|\.)(mock|fixture|fake)\w*$/i.test(mod)) v.push(`${path}: imports '${mod}'`);
  }
  for (const m of text.matchAll(/^\s*(?:def|class)\s+(\w+)/gm)) if (/^_?(mock|fixture|fake)/i.test(m[1])) v.push(`${path}: declares '${m[1]}'`);
  return v;
}

/** Checks built bundle text for test-module names. */
export function checkBundle(path, text) {
  return NAME.test(text) ? [`${path}: bundle contains '${text.match(NAME)[0]}'`] : [];
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const v = [];
  for (const f of trackedFiles(['src'])) {
    if (!/\.[cm]?[jt]sx?$/.test(f) || TEST_FILE.test(f)) continue;
    v.push(...checkTsSource(f, read(f)));
  }
  for (const f of trackedFiles(['avenel', 'apps'])) if (f.endsWith('.py')) v.push(...checkPySource(f, read(f)));
  const dist = walk('dist').filter((f) => /\.(js|css|html)$/.test(f));
  if (dist.length === 0) v.push('dist/ is empty: run `npm run build` first');
  for (const f of dist) v.push(...checkBundle(f, read(f)));
  report('no_test_code_in_prod', v);
}
