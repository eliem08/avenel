import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { checkCss } from './check_css_palette.mjs';

describe('Part E palette guard', () => {
  it('flags default Tailwind palette classes', () => {
    expect(checkCss('.bg-slate-50{background:#f8fafc}')).not.toHaveLength(0);
    expect(checkCss('.hover\:text-indigo-600:hover{color:rgb(79 70 229)}')).not.toHaveLength(0);
    expect(checkCss('.text-white{color:#fff}')).not.toHaveLength(0);
  });
  it('flags non Part E colour literals', () => {
    expect(checkCss('.x{color:#D93874}')).toEqual(['colour not in Part E: #D93874']);
  });
  it('accepts Part E tokens with opacity', () => {
    expect(checkCss('.bg-sky{background:rgb(5 147 198 / .5)}.text-ink-2{color:#4a6573}.b{border:#0593c64d}')).toEqual([]);
  });
  it('the built CSS passes (run after `npm run build`)', () => {
    const dir = 'dist/assets';
    if (!existsSync(dir)) throw new Error('dist/assets missing: run `npm run build` before this test');
    const css = readdirSync(dir).filter((f) => f.endsWith('.css')).map((f) => readFileSync(`${dir}/${f}`, 'utf8')).join('\n');
    expect(checkCss(css)).toEqual([]);
  });
});
