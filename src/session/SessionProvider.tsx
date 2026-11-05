import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useApi } from '@/api/useApi';
import type { UserSession } from '@/api/client';

/** Active membership from GET /v1/me. The API stays the authority on every action. */
interface SessionValue {
  me: UserSession | null;
  state: 'loading' | 'ready' | 'error';
}

const SessionContext = createContext<SessionValue>({ me: null, state: 'loading' });

export function SessionProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [value, setValue] = useState<SessionValue>({ me: null, state: 'loading' });
  useEffect(() => {
    let alive = true;
    api
      .GET('/me')
      .then(({ data }) => alive && setValue(data ? { me: data, state: 'ready' } : { me: null, state: 'error' }))
      .catch(() => alive && setValue({ me: null, state: 'error' }));
    return () => {
      alive = false;
    };
  }, [api]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  return useContext(SessionContext);
}

// Mirrors the role checks in apps/api/routes (clients, periods, chart, compliance).
// Only hides actions the API would refuse; it never grants anything.
const WRITE_ROLES = new Set(['owner', 'manager', 'accountant']);
const ARCHIVE_ROLES = new Set(['owner', 'manager']);

export function can(me: UserSession | null, action: 'write' | 'archive' | 'compliance'): boolean {
  if (!me) return false;
  if (action === 'write') return WRITE_ROLES.has(me.role);
  if (action === 'archive') return ARCHIVE_ROLES.has(me.role);
  return me.role !== 'client_user';
}
