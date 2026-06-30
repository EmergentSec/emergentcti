import { useState } from 'react'
import { Key, Users, SlidersHorizontal } from '@phosphor-icons/react'
import { ApiKeyManager } from '@/components/settings/ApiKeyManager'
import { GeneralSettings } from '@/components/settings/GeneralSettings'
import { UserManager } from '@/components/settings/UserManager'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'

type Tab = 'apikeys' | 'members' | 'general'

interface NavItem {
  id: Tab
  label: string
  Icon: React.ElementType
  adminOnly: boolean
}

const NAV_ITEMS: NavItem[] = [
  { id: 'apikeys', label: 'API keys', Icon: Key, adminOnly: true },
  { id: 'members', label: 'Members', Icon: Users, adminOnly: true },
  { id: 'general', label: 'General', Icon: SlidersHorizontal, adminOnly: false },
]

export default function SettingsPage() {
  const { isAdmin } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>(isAdmin ? 'apikeys' : 'general')

  const visibleItems = NAV_ITEMS.filter(item => !item.adminOnly || isAdmin)

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
        {activeTab === 'general' && <GeneralSettings />}
      </div>
    </div>
  )
}
