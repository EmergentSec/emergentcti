import { useSearchParams } from 'react-router-dom'
import { Export, Key, ShieldCheck, Users, SlidersHorizontal, UserCircle } from '@phosphor-icons/react'
import { AccountSettings } from '@/components/settings/AccountSettings'
import { AllowlistManager } from '@/components/settings/AllowlistManager'
import { ApiKeyManager } from '@/components/settings/ApiKeyManager'
import { ExportProfileManager } from '@/components/settings/ExportProfileManager'
import { GeneralSettings } from '@/components/settings/GeneralSettings'
import { UserManager } from '@/components/settings/UserManager'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'

type Tab = 'apikeys' | 'members' | 'allowlist' | 'exportprofiles' | 'account' | 'general'

interface NavItem {
  id: Tab
  label: string
  Icon: React.ElementType
  adminOnly: boolean
}

const NAV_ITEMS: NavItem[] = [
  { id: 'apikeys', label: 'API keys', Icon: Key, adminOnly: true },
  { id: 'members', label: 'Members', Icon: Users, adminOnly: true },
  // Readable by every signed-in user; the panes hide mutation controls from non-admins.
  { id: 'allowlist', label: 'Allowlist', Icon: ShieldCheck, adminOnly: false },
  { id: 'exportprofiles', label: 'Export profiles', Icon: Export, adminOnly: false },
  { id: 'account', label: 'Account', Icon: UserCircle, adminOnly: false },
  { id: 'general', label: 'General', Icon: SlidersHorizontal, adminOnly: false },
]

export default function SettingsPage() {
  const { isAdmin } = useAuth()
  const visibleItems = NAV_ITEMS.filter(item => !item.adminOnly || isAdmin)

  // Follow router navigation, including deep links while Settings stays mounted.
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('tab')
  const activeTab: Tab = visibleItems.find(item => item.id === requested)?.id
    ?? (isAdmin ? 'apikeys' : 'account')
  const setActiveTab = (tab: Tab) => {
    const params = new URLSearchParams(searchParams)
    params.set('tab', tab)
    setSearchParams(params)
  }

  return (
    <div className="flex gap-6">
      {/* Left vertical sub-nav */}
      <nav className="w-48 shrink-0">
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          {visibleItems.map(item => {
            const isActive = activeTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex w-full items-center gap-3 px-3 py-2.5 text-sm transition-colors',
                  isActive
                    ? 'font-bold text-brand'
                    : 'font-medium text-muted-foreground hover:text-foreground hover:bg-hover',
                )}
                style={
                  isActive
                    ? { background: 'color-mix(in srgb, var(--brand) 13%, transparent)' }
                    : undefined
                }
              >
                <item.Icon size={16} />
                {item.label}
              </button>
            )
          })}
        </div>
      </nav>

      {/* Right content pane */}
      <div className="min-w-0 flex-1">
        {activeTab === 'apikeys' && isAdmin && <ApiKeyManager />}
        {activeTab === 'members' && isAdmin && <UserManager />}
        {activeTab === 'allowlist' && <AllowlistManager />}
        {activeTab === 'exportprofiles' && <ExportProfileManager />}
        {activeTab === 'account' && <AccountSettings />}
        {activeTab === 'general' && <GeneralSettings />}
      </div>
    </div>
  )
}
