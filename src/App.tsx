import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireAuth } from '@/auth/AuthProvider';
import { AppShell } from '@/shell/AppShell';
import { LoginScreen } from '@/screens/LoginScreen';
import { CallbackScreen } from '@/screens/CallbackScreen';
import { SilentRenewScreen } from '@/screens/SilentRenewScreen';
import { QueueScreen } from '@/screens/QueueScreen';
import { LaterScreen } from '@/screens/LaterScreen';

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LoginScreen />} />
          <Route path="/callback" element={<CallbackScreen />} />
          <Route path="/silent-renew" element={<SilentRenewScreen />} />
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/queue" element={<QueueScreen />} />
            <Route path="/clients" element={<LaterScreen title="Clients" />} />
            <Route path="/approvals" element={<LaterScreen title="Validations" />} />
            <Route path="/settings" element={<LaterScreen title="Paramètres" />} />
          </Route>
          <Route
            path="*"
            element={
              <RequireAuth>
                <Navigate to="/queue" replace />
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
