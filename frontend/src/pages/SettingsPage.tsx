import { ApiKeyManager } from '@/components/settings/ApiKeyManager'
import { GeneralSettings } from '@/components/settings/GeneralSettings'

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <ApiKeyManager />
      <GeneralSettings />
    </div>
  )
}
