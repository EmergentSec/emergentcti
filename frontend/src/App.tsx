import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/contexts/AuthContext';
import { ToastProvider } from '@/contexts/ToastContext';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { AppLayout } from '@/components/layout/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { ObservablesPage } from '@/pages/ObservablesPage';
import { ObservableDetailPage } from '@/pages/ObservableDetailPage';
import { FeedsPage } from '@/pages/FeedsPage';
import { SearchPage } from '@/pages/SearchPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { UsersPage } from '@/pages/UsersPage';
import { AttackMatrixPage } from '@/pages/AttackMatrixPage';
import { ThreatActorsPage } from '@/pages/ThreatActorsPage';
import { ThreatActorDetailPage } from '@/pages/ThreatActorDetailPage';
import { CampaignsPage } from '@/pages/CampaignsPage';
import { CampaignDetailPage } from '@/pages/CampaignDetailPage';
import { ImportPage } from '@/pages/ImportPage';
import { AlertsPage } from '@/pages/AlertsPage';
import { CorrelationsPage } from '@/pages/CorrelationsPage';
import { ActivityPage } from '@/pages/ActivityPage';
import { GraphExplorerPage } from '@/pages/GraphExplorerPage';
import { ReportsPage } from '@/pages/ReportsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <AuthProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<AppLayout />}>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/observables" element={<ObservablesPage />} />
                  <Route
                    path="/observables/:id"
                    element={<ObservableDetailPage />}
                  />
                  <Route path="/threat-actors" element={<ThreatActorsPage />} />
                  <Route
                    path="/threat-actors/:id"
                    element={<ThreatActorDetailPage />}
                  />
                  <Route path="/campaigns" element={<CampaignsPage />} />
                  <Route
                    path="/campaigns/:id"
                    element={<CampaignDetailPage />}
                  />
                  <Route path="/attack" element={<AttackMatrixPage />} />
                  <Route path="/feeds" element={<FeedsPage />} />
                  <Route path="/import" element={<ImportPage />} />
                  <Route path="/alerts" element={<AlertsPage />} />
                  <Route path="/correlations" element={<CorrelationsPage />} />
                  <Route path="/graph" element={<GraphExplorerPage />} />
                  <Route
                    path="/graph/:entityType/:entityId"
                    element={<GraphExplorerPage />}
                  />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/activity" element={<ActivityPage />} />
                  <Route path="/search" element={<SearchPage />} />
                  <Route path="/users" element={<UsersPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </AuthProvider>
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
