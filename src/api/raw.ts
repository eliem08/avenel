import { useCallback } from 'react';
import { useAuth } from '@/auth/AuthProvider';
import { config } from '@/config';

/**
 * Authenticated fetch for binary endpoints the typed client does not model well
 * (file upload body, PNG page images). Same in-memory token; mutating calls get a
 * fresh Idempotency-Key, like the typed client.
 */
export function useRawFetch() {
  const { user } = useAuth();
  const token = user?.access_token;
  return useCallback(
    (path: string, init: RequestInit = {}) => {
      const headers = new Headers(init.headers);
      if (token) headers.set('Authorization', `Bearer ${token}`);
      const method = (init.method ?? 'GET').toUpperCase();
      if (method !== 'GET' && !headers.has('Idempotency-Key')) headers.set('Idempotency-Key', crypto.randomUUID());
      return fetch(`${config.apiBaseUrl}${path}`, { ...init, headers });
    },
    [token],
  );
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}
