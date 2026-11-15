// Demo helper (local test realm only): prints each demo user's current one-time code and its password
// source, so a live demo can log in without an authenticator app. Never point this at a real realm.
// Usage: node scripts/demo-otp.mjs            (codes change every 30 s; run again if one is refused)
import { readFileSync } from 'node:fs';
import { Secret, TOTP } from 'otpauth';

const realm = JSON.parse(readFileSync('docker/keycloak/realm-export-test.json', 'utf8'));
const roles = {
  'ci-accountant@test.internal': 'comptable (cabinet)',
  'ci-expert@test.internal': 'expert-comptable (approuve)',
  'ci-client@test.internal': 'client (Atlas uniquement)',
};
const left = 30 - Math.floor(Date.now() / 1000) % 30;
console.log(`Codes valables encore ${left} s. Mots de passe : docker/keycloak/realm-export-test.json\n`);
for (const u of realm.users) {
  const otp = JSON.parse(u.credentials.find((c) => c.type === 'otp')?.secretData ?? '{}').value;
  if (!otp) continue;
  const code = new TOTP({ secret: Secret.fromLatin1(otp), digits: 6, period: 30, algorithm: 'SHA1' }).generate();
  console.log(`${u.username.padEnd(30)} ${code}   ${roles[u.username] ?? ''}`);
}
