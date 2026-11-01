import { useSearchParams } from 'react-router-dom'
import { Export, Key, ShieldCheck, Users, SlidersHorizontal, UserCircle } from '@phosphor-icons/react'
import { AccountSettings } from '@/components/settings/AccountSettings'
import { AllowlistManager } from '@/components/settings/AllowlistManager'
import { ApiKeyManager } from '@/components/settings/ApiKeyManager'
import { ExportProfileManager } from '@/components/settings/ExportProfileManager'
import { GeneralSettings } from '@/components/settings/GeneralSettings'
import { UserManager } from '@/components/settings/UserManager'
import { Card } from '@/components/ui/Card'
import { Tabs } from '@/components/ui/Tabs'
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
  { id: 'allowlist', label: 'Allowlist', Icon: ShieldCheck, adminOnly: false },
  { id: 'exportprofiles', label: 'Export profiles', Icon: Export, adminOnly: false },
  { id: 'account', label: 'Account', Icon: UserCircle, adminOnly: false },
  { id: 'general', label: 'General', Icon: SlidersHorizontal, adminOnly: false },
]

export default function SettingsPage() {
  const { isAdmin } = useAuth()
  const visibleItems = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin)
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('tab')
  const activeTab: Tab = visibleItems.find((item) => item.id === requested)?.id
    ?? (isAdmin ? 'apikeys' : 'account')

  const setActiveTab = (tab: Tab) => {
    const params = new URLSearchParams(searchParams)
    params.set('tab', tab)
    setSearchParams(params)
  }

  return (
    <div className="flex min-w-0 flex-col gap-5 md:flex-row md:items-start md:gap-6">
      <Tabs
        tabs={visibleItems.map((item) => ({ key: item.id, label: item.label }))}
        active={activeTab}
        onChange={(key) => setActiveTab(key as Tab)}
        className="w-full md:hidden"
      />

      <nav aria-label="Settings sections" className="hidden w-48 shrink-0 md:block">
        <Card className="overflow-hidden p-1.5">
          {visibleItems.map((item) => {
            const isActive = activeTab === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveTab(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors',
                  isActive
                    ? 'bg-primary-soft font-semibold text-primary'
                    : 'font-medium text-muted-foreground hover:bg-hover hover:text-foreground',
                )}
              >
                <item.Icon size={16} aria-hidden="true" />
                {item.label}
              </button>
            )
          })}
        </Card>
      </nav>

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
