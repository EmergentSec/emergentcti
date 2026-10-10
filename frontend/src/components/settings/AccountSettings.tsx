import { useState } from 'react'
import { isAxiosError } from 'axios'
import { useChangePassword } from '@/hooks/useUsers'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'

// Mirrors the backend PasswordChange schema (new_password: 8–128 chars).
const MIN_PASSWORD_LENGTH = 8
const MAX_PASSWORD_LENGTH = 128

/** Prefer the API's `detail` string (e.g. "Current password is incorrect"). */
function errorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    // FastAPI validation errors: [{ msg, ... }]
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg
  }
  return err instanceof Error ? err.message : 'Failed to change password'
}

export function AccountSettings() {
  const { user } = useAuth()
  const { toast } = useToast()
  const changePassword = useChangePassword()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  if (!user) return null

  const newPasswordError =
    newPassword && newPassword.length < MIN_PASSWORD_LENGTH
      ? `Must be at least ${MIN_PASSWORD_LENGTH} characters`
      : undefined
  const confirmError =
    confirmPassword && confirmPassword !== newPassword ? 'Passwords do not match' : undefined

  const canSubmit =
    currentPassword.length > 0 &&
    newPassword.length >= MIN_PASSWORD_LENGTH &&
    confirmPassword === newPassword &&
    !changePassword.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    changePassword.mutate(
      { id: user.id, data: { new_password: newPassword, current_password: currentPassword } },
      {
        onSuccess: () => {
          toast('Password changed successfully', 'success')
          setCurrentPassword('')
          setNewPassword('')
          setConfirmPassword('')
        },
        onError: (err) => {
          toast(errorMessage(err), 'error')
        },
      },
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between border-b border-border py-3">
            <p className="text-sm text-muted-foreground">Username</p>
            <span className="font-mono text-sm text-foreground">{user.username}</span>
          </div>
          <div className="flex items-center justify-between py-3">
            <p className="text-sm text-muted-foreground">Role</p>
            <Badge
              variant={user.role === 'admin' ? 'default' : 'secondary'}
              className={user.role === 'admin' ? 'bg-brand text-brand-foreground' : ''}
            >
              {user.role === 'admin' ? 'Admin' : 'User'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="max-w-sm space-y-4">
            <Input
              label="Current password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
            <Input
              label="New password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              maxLength={MAX_PASSWORD_LENGTH}
              error={newPasswordError}
              required
            />
            <Input
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              maxLength={MAX_PASSWORD_LENGTH}
              error={confirmError}
              required
            />
            <p className="text-xs text-muted-foreground">
              Changing your password signs you out on other devices. You stay signed in here.
            </p>
            <div className="flex justify-end">
              <Button type="submit" disabled={!canSubmit}>
                {changePassword.isPending ? 'Saving...' : 'Change Password'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
