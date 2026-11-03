import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { User, UserManager } from 'oidc-client-ts';
import { STEP_UP_MAX_AGE_SECONDS, createUserManager, hasFreshMfa } from './oidc';

interface AuthContextValue {
  user: User | null;
  ready: boolean;
  login: (returnTo?: string) => Promise<void>;
  logout: () => Promise<void>;
  completeLogin: () => Promise<string>;
  /** Forces a new login with MFA unless the current one is fresh (≤ 5 min). */
  requireFreshMfa: (returnTo: string) => Promise<boolean>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, manager }: { children: ReactNode; manager?: UserManager }) {
  const um = useMemo(() => manager ?? createUserManager(), [manager]);
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    um.getUser().then((u) => {
      if (alive) {
        setUser(u && !u.expired ? u : null);
        setReady(true);
      }
    });
    const onLoaded = (u: User) => setUser(u);
    const onUnloaded = () => setUser(null);
    um.events.addUserLoaded(onLoaded);
    um.events.addUserUnloaded(onUnloaded);
    um.events.addSilentRenewError(onUnloaded);
    return () => {
      alive = false;
      um.events.removeUserLoaded(onLoaded);
      um.events.removeUserUnloaded(onUnloaded);
      um.events.removeSilentRenewError(onUnloaded);
    };
  }, [um]);

  const login = useCallback((returnTo = '/queue') => um.signinRedirect({ state: { returnTo } }), [um]);
  const logout = useCallback(async () => {
    const idToken = user?.id_token;
    await um.removeUser();
    setUser(null);
    await um.signoutRedirect({ id_token_hint: idToken });
  }, [um, user]);
  const completeLogin = useCallback(async () => {
    const u = await um.signinRedirectCallback();
    setUser(u);
    const st = u.state as { returnTo?: string } | undefined;
    return st?.returnTo ?? '/queue';
  }, [um]);
  const requireFreshMfa = useCallback(
    async (returnTo: string) => {
      if (hasFreshMfa(user)) return true;
      await um.signinRedirect({ prompt: 'login', max_age: STEP_UP_MAX_AGE_SECONDS, state: { returnTo } });
      return false;
    },
    [um, user],
  );

  const value = useMemo(
    () => ({ user, ready, login, logout, completeLogin, requireFreshMfa }),
    [user, ready, login, logout, completeLogin, requireFreshMfa],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth outside AuthProvider');
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return null;
  if (!user) return <Navigate to="/" replace state={{ returnTo: location.pathname }} />;
  return <>{children}</>;
}
