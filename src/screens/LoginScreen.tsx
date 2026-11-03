import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/auth/AuthProvider';
import { Button } from '@/components/ui/Button';

export function LoginScreen() {
  const { user, ready, login } = useAuth();
  const location = useLocation();
  const returnTo = (location.state as { returnTo?: string } | null)?.returnTo ?? '/queue';
  if (ready && user) return <Navigate to={returnTo} replace />;
  return (
    <main className="min-h-screen bg-paper px-12 py-16">
      <p className="font-heading text-xl font-semibold text-sky-ink">AVENEL</p>
      <h1 className="mt-10 text-[1.75rem] text-ink">Connexion</h1>
      <p className="mt-2 max-w-[75ch] text-base text-ink-2">
        Accédez aux dossiers mensuels de votre cabinet. La connexion se fait avec votre compte et un code à usage unique.
      </p>
      <Button className="mt-6" onClick={() => void login(returnTo)} disabled={!ready} data-testid="btn-login">
        Se connecter
      </Button>
    </main>
  );
}
