import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

interface AppLayoutProps {
  apiKeyPrefix?: string
  onLogout?: () => void
}

export function AppLayout({ apiKeyPrefix, onLogout }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Sidebar />
      <div className="pl-60">
        <Header apiKeyPrefix={apiKeyPrefix} onLogout={onLogout} />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppLayout
