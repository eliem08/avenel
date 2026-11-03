import { useMemo } from 'react';
import { useAuth } from '@/auth/AuthProvider';
import { createApiClient } from './client';

export function useApi() {
  const { user } = useAuth();
  const token = user?.access_token;
  return useMemo(() => createApiClient(() => token), [token]);
}
