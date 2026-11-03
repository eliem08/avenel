// Part K 28: e2e must not run unless the docker-compose stack is healthy.
// Polls the API readiness probe, Keycloak realm discovery and the web container; exits 1 on timeout.
const CHECKS = [
  ['api /health/ready', process.env.E2E_API_HEALTH ?? 'http://localhost:8000/health/ready'],
  ['keycloak realm', process.env.E2E_KC_DISCOVERY ?? 'http://localhost:8080/realms/avenel/.well-known/openid-configuration'],
  ['web /healthz', process.env.E2E_WEB_HEALTH ?? 'http://localhost:5173/healthz'],
];
const deadline = Date.now() + Number(process.env.E2E_HEALTH_TIMEOUT_MS ?? 300_000);

async function ok(url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(5000) });
    return r.status === 200 ? await r.text() : `HTTP ${r.status}`;
  } catch (e) {
    return null;
  }
}

for (const [name, url] of CHECKS) {
  let last = null;
  for (;;) {
    last = await ok(url);
    if (last && !last.startsWith('HTTP ')) break;
    if (Date.now() > deadline) {
      console.error(`wait_for_stack: ${name} NOT green at ${url} (last: ${last ?? 'no response'})`);
      process.exit(1);
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  console.log(`wait_for_stack: ${name} green: ${url} ${last.slice(0, 160).replace(/\s+/g, ' ')}`);
}
