import { InMemoryWebStorage, UserManager, WebStorageStateStore, type User } from 'oidc-client-ts';
import { config } from '@/config';

/**
 * Tokens (access, refresh, id) live in memory only: never localStorage or sessionStorage.
 * The one exception is the single-use authorization request state (PKCE code_verifier,
 * state, nonce): it must survive the full-page redirect to Keycloak, so it sits in
 * sessionStorage for the duration of the redirect and oidc-client-ts deletes it when
 * /callback completes. It is not a credential: without the authorization code it is useless.
 */
export function createUserManager(origin: string = window.location.origin): UserManager {
  return new UserManager({
    authority: config.oidcAuthority,
    client_id: config.oidcClientId,
    redirect_uri: `${origin}/callback`,
    silent_redirect_uri: `${origin}/silent-renew`,
    post_logout_redirect_uri: `${origin}/`,
    response_type: 'code', // Authorization Code; oidc-client-ts always uses PKCE S256 for code flow
    scope: 'openid profile email',
    automaticSilentRenew: true,
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage, prefix: 'avenel.oidc.' }),
    monitorSession: false,
  });
}

/** Max age of an MFA authentication for approval actions (Part K 5, RFC 9470). */
export const STEP_UP_MAX_AGE_SECONDS = 300;

function decodeJwtPayload(token: string): Record<string, unknown> {
  const part = token.split('.')[1];
  if (!part) return {};
  const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'));
  return JSON.parse(json) as Record<string, unknown>;
}

/** True when the access token proves an MFA login no older than STEP_UP_MAX_AGE_SECONDS. */
export function hasFreshMfa(user: Pick<User, 'access_token'> | null, nowSeconds = Math.floor(Date.now() / 1000)): boolean {
  if (!user?.access_token) return false;
  const claims = decodeJwtPayload(user.access_token);
  const authTime = typeof claims.auth_time === 'number' ? claims.auth_time : null;
  const amr = Array.isArray(claims.amr) ? claims.amr.map((a) => String(a).toLowerCase()) : [];
  const acr = String(claims.acr ?? '').toLowerCase();
  const mfa = amr.some((a) => ['otp', 'totp', 'mfa', 'hwk'].includes(a)) || ['mfa', 'gold', '2'].includes(acr);
  return mfa && authTime !== null && nowSeconds - authTime <= STEP_UP_MAX_AGE_SECONDS;
}
