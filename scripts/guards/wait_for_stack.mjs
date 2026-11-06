// Part K 28: e2e must not run unless the docker-compose stack is healthy.
// Polls the API readiness probe, Keycloak realm discovery and the web container; exits 1 on timeout.
// Each check requires an exact body marker, so a different server on the same port cannot pass.
const CHECKS = [
  // Intake must be open: ClamAV reachable with signatures <= 48 h old (Part K 8).
  ['api /health/ready', process.env.E2E_API_HEALTH ?? 'http://localhost:8000/health/ready', '"intake_paused":false'],
  ['keycloak realm', process.env.E2E_KC_DISCOVERY ?? 'http://localhost:8080/realms/avenel/.well-known/openid-configuration', '"issuer":"http://localhost:8080/realms/avenel"'],
  ['web /healthz (nginx)', process.env.E2E_WEB_HEALTH ?? 'http://localhost:5173/healthz', 'healthy'],
];
import net from 'node:net';

// The clamav image ships an old signature database and clamd loads it before freshclam
// finishes the first download. While the API reports intake paused, ask clamd to reload.
function reloadClamd() {
  return new Promise((resolve) => {
    const sock = net.connect({ host: process.env.E2E_CLAMD_HOST ?? '127.0.0.1', port: 3310 }, () => sock.end('RELOAD' + String.fromCharCode(10)));
    sock.on('error', () => resolve(false));
    sock.on('close', () => resolve(true));
    sock.setTimeout(5000, () => sock.destroy());
  });
}

const deadline = Date.now() + Number(process.env.E2E_HEALTH_TIMEOUT_MS ?? 300_000);

async function ok(url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(5000) });
    return r.status === 200 ? await r.text() : `HTTP ${r.status}`;
  } catch (e) {
    return null;
  }
}

for (const [name, url, marker] of CHECKS) {
  let last = null;
  for (;;) {
    last = await ok(url);
    if (last && !last.startsWith('HTTP ') && last.trim().startsWith(marker.startsWith('"') ? '{' : marker) && last.includes(marker)) break;
    if (Date.now() > deadline) {
      console.error(`wait_for_stack: ${name} NOT green at ${url} (last: ${last ?? 'no response'})`);
      process.exit(1);
    }
    if (last && last.includes('"intake_paused":true')) {
      console.log('wait_for_stack: intake paused (ClamAV signatures not fresh yet), asking clamd to reload');
      await reloadClamd();
      await new Promise((r) => setTimeout(r, 20000));
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  console.log(`wait_for_stack: ${name} green: ${url} ${last.slice(0, 160).replace(/\s+/g, ' ')}`);
}
