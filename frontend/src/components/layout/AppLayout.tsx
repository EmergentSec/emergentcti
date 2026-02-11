import { Outlet, Navigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { CommandPalette } from '@/components/common/CommandPalette';

export function AppLayout() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col pl-64">
        <Header />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
