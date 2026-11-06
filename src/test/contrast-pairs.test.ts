// Part E.2 guard: no text in the same token as its own fill, and --ok / --fail / --pink are never
// solid fills under text (text, icons, markers only). Phase 3: a mechanical palette mapping had
// produced `bg-ink text-ink` buttons whose labels were invisible.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.tsx$/.test(n) && !/\.test\./.test(n) ? [p] : [];
  });
}

const CLASS = /className=(?:"([^"]*)"|\{`([^`]*)`\})/g;

describe('Part E.2 colour pairs in components', () => {
  const offenders: string[] = [];
  for (const f of files('src')) {
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(CLASS)) {
      const cls = (m[1] ?? m[2] ?? '').split(/\s+/).filter((c) => !c.includes(':'));
      const bg = cls.find((c) => /^bg-(ink|sky|pink|ok|fail)(-ink|-2)?$/.test(c));
      const text = cls.find((c) => /^text-(ink|sky|pink|ok|fail|paper)(-ink|-2)?$/.test(c));
      if (!bg || !text) continue;
      const bgTok = bg.slice(3);
      if (text.slice(5) === bgTok) offenders.push(`${f}: ${bg} + ${text}`);
      if (/^(ok|fail|pink)$/.test(bgTok)) offenders.push(`${f}: ${bg} used as a fill under ${text}`);
    }
  }
  it('has no same-token or forbidden status fills under text', () => {
    expect(offenders).toEqual([]);
  });
});
