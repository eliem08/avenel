import { describe, expect, it } from 'vitest';
import { User } from 'oidc-client-ts';
import { createUserManager, hasFreshMfa, STEP_UP_MAX_AGE_SECONDS } from './oidc';

function token(claims: Record<string, unknown>): string {
  const b64 = (o: unknown) => btoa(JSON.stringify(o)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${b64({ alg: 'none' })}.${b64(claims)}.sig`;
}

describe('hasFreshMfa (step-up, Part K 5)', () => {
  const now = 1_800_000_000;
  it('accepts OTP login within 5 minutes', () => {
    expect(hasFreshMfa({ access_token: token({ amr: ['pwd', 'otp'], auth_time: now - 60 }) }, now)).toBe(true);
  });
  it('rejects OTP login older than 5 minutes', () => {
    expect(
      hasFreshMfa({ access_token: token({ amr: ['otp'], auth_time: now - STEP_UP_MAX_AGE_SECONDS - 1 }) }, now),
    ).toBe(false);
  });
  it('rejects a fresh login without MFA', () => {
    expect(hasFreshMfa({ access_token: token({ amr: ['pwd'], auth_time: now }) }, now)).toBe(false);
  });
  it('rejects a token without auth_time', () => {
    expect(hasFreshMfa({ access_token: token({ amr: ['otp'] }) }, now)).toBe(false);
  });
  it('rejects no user', () => {
    expect(hasFreshMfa(null, now)).toBe(false);
  });
});

describe('token storage', () => {
  it('keeps the user and OIDC state in memory, never in Web Storage', async () => {
    localStorage.clear();
    sessionStorage.clear();
    const um = createUserManager('http://localhost:5173');
    await um.storeUser(
      new User({ access_token: 'a.b.c', token_type: 'Bearer', profile: { sub: 's', iss: 'i', aud: 'a', exp: 0, iat: 0 } }),
    );
    expect(await um.getUser()).not.toBeNull();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('uses Authorization Code flow (PKCE) with in-memory stores', () => {
    const um = createUserManager('http://localhost:5173');
    expect(um.settings.response_type).toBe('code');
    expect(um.settings.redirect_uri).toBe('http://localhost:5173/callback');
  });
});
