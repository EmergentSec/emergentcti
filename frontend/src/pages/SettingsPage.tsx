import { ApiKeyManager } from '@/components/settings/ApiKeyManager'
import { GeneralSettings } from '@/components/settings/GeneralSettings'
import { UserManager } from '@/components/settings/UserManager'
import { useAuth } from '@/contexts/AuthContext'

export default function SettingsPage() {
  const { isAdmin } = useAuth()

  return (
    <div className="space-y-6">
      {isAdmin && <UserManager />}
      <ApiKeyManager />
      <GeneralSettings />
    </div>
  )
}
