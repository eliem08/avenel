// Part K 26: e2e tests never intercept or fake network traffic.
import { fileURLToPath } from 'node:url';
import { read, report, trackedFiles } from './lib.mjs';

const FORBIDDEN = [
  /\.route\s*\(/, // page.route, context.route, browserContext.route
  /\.routeFromHAR\s*\(/,
  /\.routeWebSocket\s*\(/,
  /\broute\.(fulfill|abort|continue|fallback)\s*\(/,
  /\.unroute(All)?\s*\(/,
  /\.setOffline\s*\(/,
  /\bserviceWorkers\s*:\s*['"]allow['"]/,
  /\bmsw\b|setupServer\s*\(|setupWorker\s*\(/,
  /\bnock\s*\(/,
];

export function checkE2e(path, text) {
  const code = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  return FORBIDDEN.filter((rx) => rx.test(code)).map((rx) => `${path}: network interception ${rx}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const files = trackedFiles(['e2e', 'playwright.config.ts']).filter((f) => /\.[cm]?[jt]s$/.test(f));
  const v = files.flatMap((f) => checkE2e(f, read(f)));
  if (!files.some((f) => f.startsWith('e2e/'))) v.push('no e2e files found');
  report('no_e2e_interception', v);
}
