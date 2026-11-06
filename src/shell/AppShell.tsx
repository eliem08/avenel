import { NavLink, Outlet } from 'react-router-dom';
import { CheckSquare, Inbox, LogOut, MessageSquare, Settings, Users } from 'lucide-react';
import { useAuth } from '@/auth/AuthProvider';
import { useSession } from '@/session/SessionProvider';
import { ToastViewport } from '@/components/ui/ToastViewport';

const NAV = [
  { to: '/queue', label: 'File de travail', Icon: Inbox },
  { to: '/clients', label: 'Clients', Icon: Users },
  { to: '/approvals', label: 'Validations', Icon: CheckSquare },
  { to: '/settings', label: 'Paramètres', Icon: Settings },
];

// Client users (portal): their files, their company, and what the firm is waiting for.
const CLIENT_NAV = [
  { to: '/queue', label: 'File de travail', Icon: Inbox },
  { to: '/clients', label: 'Société', Icon: Users },
  { to: '/portal', label: 'Demandes du cabinet', Icon: MessageSquare },
];

/**
 * GET /v1/me returns the single active membership resolved from the token.
 * The switcher lists exactly what the API returns; multi-firm listing needs an
 * endpoint that does not exist yet.
 */
function FirmSwitcher() {
  const { me } = useSession();
  return (
    <label className="block px-4 pb-4">
      <span className="text-[0.8125rem] text-ink-2">Cabinet</span>
      <select
        className="mt-1 h-9 w-full rounded-input border border-line bg-paper px-2 text-sm text-ink"
        data-testid="firm-switcher"
        data-tenant-id={me?.tenant_id ?? ''}
        disabled={!me}
        value={me?.tenant_id ?? ''}
        onChange={() => undefined}
      >
        {me ? <option value={me.tenant_id}>Cabinet {me.tenant_id.slice(0, 8)}</option> : <option value="">…</option>}
      </select>
    </label>
  );
}

export function AppShell() {
  const { logout, user } = useAuth();
  const { me } = useSession();
  return (
    <div className="flex min-h-screen bg-paper text-ink">
      <nav aria-label="Navigation principale" className="flex w-rail shrink-0 flex-col border-r border-line bg-surface">
        <p className="px-4 py-5 font-heading text-xl font-semibold text-sky-ink">AVENEL</p>
        <FirmSwitcher />
        <ul className="flex-1">
          {(me?.role === 'client_user' ? CLIENT_NAV : NAV).map(({ to, label, Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `flex h-10 items-center gap-3 border-l-2 px-4 text-sm ${
                    isActive ? 'border-l-sky bg-sky-wash text-ink' : 'border-l-transparent text-ink-2 hover:bg-paper'
                  }`
                }
              >
                <Icon size={20} strokeWidth={1.5} aria-hidden="true" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="border-t border-line px-4 py-3">
          <p className="truncate text-[0.8125rem] text-ink-2" data-testid="user-email">
            {user?.profile.email}
          </p>
          <button
            type="button"
            onClick={() => void logout()}
            className="mt-2 flex items-center gap-2 text-sm text-sky-ink"
            data-testid="btn-logout"
          >
            <LogOut size={16} strokeWidth={1.5} aria-hidden="true" />
            Se déconnecter
          </button>
        </div>
      </nav>
      <main className="flex-1 px-8 py-6">
        <Outlet />
      </main>
      <ToastViewport />
    </div>
  );
}
