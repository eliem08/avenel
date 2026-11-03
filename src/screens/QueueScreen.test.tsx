// STUBBED: these unit tests replace window.fetch to drive the loading, empty and
// error states. The real-stack behaviour is covered by e2e/login-queue.spec.ts.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserManager } from 'oidc-client-ts';
import { AuthProvider } from '@/auth/AuthProvider';
import { QueueScreen } from './QueueScreen';

const stubManager = {
  getUser: async () => null,
  events: {
    addUserLoaded: () => undefined,
    addUserUnloaded: () => undefined,
    addSilentRenewError: () => undefined,
    removeUserLoaded: () => undefined,
    removeUserUnloaded: () => undefined,
    removeSilentRenewError: () => undefined,
  },
} as unknown as UserManager;

function renderQueue() {
  return render(
    <MemoryRouter>
      <AuthProvider manager={stubManager}>
        <QueueScreen />
      </AuthProvider>
    </MemoryRouter>,
  );
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

afterEach(() => vi.unstubAllGlobals());

describe('QueueScreen states (stubbed fetch)', () => {
  it('shows the error state when the API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    renderQueue();
    expect(await screen.findByTestId('state-error')).toHaveTextContent("Les dossiers n'ont pas pu être chargés.");
  });

  it('shows the empty state for an empty list', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ items: [] })));
    renderQueue();
    expect(await screen.findByTestId('state-empty')).toBeInTheDocument();
  });

  it('shows rows with client names and marks awaiting approval with the pink rule', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (req: Request) =>
        req.url.includes('/work-requests')
          ? json({ items: [{ id: 'w1', tenant_id: 't', client_entity_id: 'c1', accounting_period_id: 'p', status: 'awaiting_approval', current_revision: 2 }] })
          : json({ items: [{ id: 'c1', tenant_id: 't', legal_name: 'Société A', functional_currency: 'MAD' }] }),
      ),
    );
    renderQueue();
    const row = await screen.findByTestId('queue-row');
    expect(row).toHaveTextContent('Société A');
    expect(row).toHaveTextContent('À valider');
    expect(row.className).toContain('border-l-pink');
  });

  it('shows the loading state first', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)));
    renderQueue();
    expect(screen.getByTestId('state-loading')).toBeInTheDocument();
  });
});
