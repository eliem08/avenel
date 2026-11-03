// Runtime configuration from Vite env (see .env.example). No secrets: the SPA is a public OIDC client.
export const config = {
  oidcAuthority: import.meta.env.VITE_OIDC_AUTHORITY ?? 'http://localhost:8080/realms/avenel',
  oidcClientId: import.meta.env.VITE_OIDC_CLIENT_ID ?? 'avenel-web',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/v1',
};
