import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth/AuthProvider';
import { ErrorState, LoadingState } from '@/components/ui/States';

export function CallbackScreen() {
  const { completeLogin } = useAuth();
  const navigate = useNavigate();
  const [failed, setFailed] = useState(false);
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    completeLogin()
      .then((to) => navigate(to, { replace: true }))
      .catch(() => setFailed(true));
  }, [completeLogin, navigate]);
  return (
    <main className="px-12 py-16">
      {failed ? (
        <ErrorState title="La connexion a échoué." detail="Revenez à la page de connexion et recommencez." />
      ) : (
        <LoadingState label="Connexion en cours…" />
      )}
    </main>
  );
}
