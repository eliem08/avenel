import { useEffect } from 'react';
import { createUserManager } from '@/auth/oidc';

/** Iframe target used only if the refresh-token renewal is unavailable. */
export function SilentRenewScreen() {
  useEffect(() => {
    void createUserManager().signinSilentCallback();
  }, []);
  return null;
}
