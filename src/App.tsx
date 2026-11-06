import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireAuth } from '@/auth/AuthProvider';
import { AppShell } from '@/shell/AppShell';
import { LoginScreen } from '@/screens/LoginScreen';
import { CallbackScreen } from '@/screens/CallbackScreen';
import { SilentRenewScreen } from '@/screens/SilentRenewScreen';
import { QueueScreen } from '@/screens/QueueScreen';
import { LaterScreen } from '@/screens/LaterScreen';
import { ClientsScreen } from '@/screens/ClientsScreen';
import { ClientScreen } from '@/screens/ClientScreen';
import { SettingsScreen } from '@/screens/SettingsScreen';
import { SessionProvider } from '@/session/SessionProvider';
import { FileScreen } from '@/screens/FileScreen';
import { DocumentScreen } from '@/screens/DocumentScreen';
import { ReviewScreen } from '@/screens/ReviewScreen';

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
                <SessionProvider>
                  <AppShell />
                </SessionProvider>
              </RequireAuth>
            }
          >
            <Route path="/queue" element={<QueueScreen />} />
            <Route path="/files/:id" element={<FileScreen />} />
            <Route path="/files/:id/review" element={<ReviewScreen />} />
            <Route path="/documents/:id" element={<DocumentScreen />} />
            <Route path="/clients" element={<ClientsScreen />} />
            <Route path="/clients/:id" element={<ClientScreen />} />
            <Route path="/approvals" element={<LaterScreen title="Validations" />} />
            <Route path="/settings" element={<SettingsScreen />} />
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
