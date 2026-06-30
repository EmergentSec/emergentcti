import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

interface AppLayoutProps {
  username?: string
  onLogout?: () => void
}

export function AppLayout({ username, onLogout }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Sidebar />
      <div className="pl-[236px]">
        <Header username={username} onLogout={onLogout} />
        <main className="mx-auto max-w-[1320px] p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppLayout
