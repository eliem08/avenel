// Part E.2 guard: built CSS may only contain Part E colours and no default Tailwind palette classes.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const PART_E_HEX = [
  '0593C6', '047AA5', 'E3F3F9', 'D83995', 'B82A7C', 'FBE8F2',
  'FCFFFF', 'F2F7F9', 'D7E3E8', '0A2533', '4A6573', '1F7A4D', 'B4232C',
];
const ALLOWED = new Set(PART_E_HEX.map((h) => h.toLowerCase()));

export const DEFAULT_PALETTE = [
  'slate', 'gray', 'zinc', 'neutral', 'stone', 'red', 'orange', 'amber', 'yellow', 'lime',
  'green', 'emerald', 'teal', 'cyan', 'blue', 'indigo', 'violet', 'purple', 'fuchsia', 'rose',
  'white', 'black',
];
const CLASS_RX = new RegExp(
  String.raw`\.[^\s{},]*?-(?:` + DEFAULT_PALETTE.join('|') + String.raw`)(?:-\d{2,3})?(?:\?/\d+)?(?![\w-])`,
  'g',
);

function toHex(lit) {
  let m = lit.match(/^#([0-9a-f]{3,8})$/i);
  if (m) {
    let h = m[1].toLowerCase();
    if (h.length === 3 || h.length === 4) h = [...h.slice(0, 3)].map((c) => c + c).join('');
    return h.slice(0, 6);
  }
  m = lit.match(/^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i);
  if (m) return m.slice(1, 4).map((n) => Number(n).toString(16).padStart(2, '0')).join('');
  return null;
}

/** Returns a list of violations (empty = pass). */
export function checkCss(css) {
  const v = [];
  for (const m of css.matchAll(CLASS_RX)) v.push(`default palette class: ${m[0]}`);
  for (const lit of new Set(css.match(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)/g) ?? [])) {
    if (lit === '#0000') continue; // fully transparent
    const hex = toHex(lit);
    if (hex && !ALLOWED.has(hex)) v.push(`colour not in Part E: ${lit}`);
  }
  return v;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dir = process.argv[2] ?? 'dist/assets';
  if (!existsSync(dir)) { console.error(`check_css_palette: ${dir} missing, run the build first`); process.exit(2); }
  const files = readdirSync(dir).filter((f) => f.endsWith('.css'));
  if (files.length === 0) { console.error('check_css_palette: no CSS in build'); process.exit(2); }
  let bad = 0;
  for (const f of files) {
    const v = checkCss(readFileSync(join(dir, f), 'utf8'));
    v.forEach((x) => console.error(`${f}: ${x}`));
    bad += v.length;
  }
  console.log(`check_css_palette: ${files.length} file(s), ${bad} violation(s)`);
  process.exit(bad ? 1 : 0);
}
