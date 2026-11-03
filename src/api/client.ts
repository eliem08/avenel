import createClient, { type Middleware } from 'openapi-fetch';
import type { paths, components } from './schema';
import { config } from '@/config';

export type WorkRequest = components['schemas']['WorkRequest'];
export type ClientEntity = components['schemas']['ClientEntity'];
export type UserSession = components['schemas']['UserSession'];

/** Typed client generated from contracts/openapi.yaml. Every call carries the in-memory bearer token. */
export function createApiClient(getToken: () => string | undefined) {
  const client = createClient<paths>({ baseUrl: config.apiBaseUrl });
  const auth: Middleware = {
    onRequest({ request }) {
      const token = getToken();
      if (token) request.headers.set('Authorization', `Bearer ${token}`);
      return request;
    },
  };
  client.use(auth);
  return client;
}

export type ApiClient = ReturnType<typeof createApiClient>;
