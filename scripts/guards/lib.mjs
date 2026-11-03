// Shared helpers for CI guards (Part K 25–28).
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

/** Tracked files (git ls-files) under the given pathspecs. */
export function trackedFiles(pathspecs) {
  const out = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', ...pathspecs], {
    encoding: 'utf8',
  });
  return out.split('\0').filter(Boolean);
}

export function walk(dir) {
  if (!existsSync(dir)) return [];
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

export function read(path) {
  return readFileSync(path, 'utf8');
}

export function report(name, violations) {
  for (const v of violations) console.error(`${name}: ${v}`);
  console.log(`${name}: ${violations.length} violation(s)`);
  process.exitCode = violations.length ? 1 : 0;
}
