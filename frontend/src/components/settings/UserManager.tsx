import { useState } from 'react'
import { useUsers, useCreateUser, useUpdateUser, useDeleteUser, useChangePassword } from '@/hooks/useUsers'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { formatRelativeTime } from '@/lib/utils'
import type { User, UserRole } from '@/types/user'

// ── Avatar helpers ────────────────────────────────────────────────────────────

/** Derive up to two initials from a username (splits on . _ - space). */
function getInitials(username: string): string {
  const parts = username.split(/[._\-\s]+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

/** Deterministic background colour from username. */
const AVATAR_PALETTE = [
  'bg-cat-blue',
  'bg-cat-green',
  'bg-cat-purple',
  'bg-cat-orange',
  'bg-cat-pink',
] as const

function avatarBg(username: string): string {
  let h = 0
  for (let i = 0; i < username.length; i++) {
    h = ((h * 31) + username.charCodeAt(i)) >>> 0
  }
  return AVATAR_PALETTE[h % AVATAR_PALETTE.length]
}

function UserAvatar({ username }: { username: string }) {
  return (
    <div
      aria-hidden="true"
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white ${avatarBg(username)}`}
    >
      {getInitials(username)}
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export function UserManager() {
  const { user: currentUser } = useAuth()
  const { toast } = useToast()

  const { data: users, isLoading, error } = useUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const deleteUser = useDeleteUser()
  const changePassword = useChangePassword()

  // Create dialog state
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<UserRole>('user')
  const [newEmail, setNewEmail] = useState('')

  // Change password dialog state
  const [passwordTarget, setPasswordTarget] = useState<User | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPasswordValue, setNewPasswordValue] = useState('')

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null)

  // Per-row pending toggle tracker (avoids disabling entire table)
  const [pendingToggleId, setPendingToggleId] = useState<string | null>(null)

  const isSelf = (user: User) => currentUser?.id === user.id

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newUsername.trim() || !newPassword.trim()) return
    createUser.mutate(
      {
        username: newUsername.trim(),
        password: newPassword.trim(),
        role: newRole,
        email: newEmail.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast('User created successfully', 'success')
          closeCreateDialog()
        },
        onError: (err) => {
          toast(err instanceof Error ? err.message : 'Failed to create user', 'error')
        },
      },
    )
  }

  const closeCreateDialog = () => {
    setShowCreate(false)
    setNewUsername('')
    setNewPassword('')
    setNewRole('user')
    setNewEmail('')
  }

  const handleToggleActive = (user: User) => {
    setPendingToggleId(user.id)
    updateUser.mutate(
      { id: user.id, data: { is_active: !user.is_active } },
      {
        onSuccess: () => {
          setPendingToggleId(null)
          toast(`${user.username} ${!user.is_active ? 'activated' : 'deactivated'}`, 'success')
        },
        onError: (err) => {
          setPendingToggleId(null)
          toast(err instanceof Error ? err.message : 'Failed to update user', 'error')
        },
      },
    )
  }

  const handleChangePassword = (e: React.FormEvent) => {
    e.preventDefault()
    if (!passwordTarget || !newPasswordValue.trim()) return
    const data = isSelf(passwordTarget)
      ? { new_password: newPasswordValue.trim(), current_password: currentPassword.trim() }
      : { new_password: newPasswordValue.trim() }
    changePassword.mutate(
      { id: passwordTarget.id, data },
      {
        onSuccess: () => {
          toast('Password changed successfully', 'success')
          closePasswordDialog()
        },
        onError: (err) => {
          toast(err instanceof Error ? err.message : 'Failed to change password', 'error')
        },
      },
    )
  }

  const closePasswordDialog = () => {
    setPasswordTarget(null)
    setCurrentPassword('')
    setNewPasswordValue('')
  }

  const handleDelete = () => {
    if (!deleteTarget) return
    deleteUser.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast(`${deleteTarget.username} deleted`, 'success')
        setDeleteTarget(null)
      },
      onError: (err) => {
        toast(err instanceof Error ? err.message : 'Failed to delete user', 'error')
        setDeleteTarget(null)
      },
    })
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Members</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage who can access this instance
          </p>
        </div>
        <Button variant="brand" onClick={() => setShowCreate(true)}>
          + Invite
        </Button>
      </div>

      {/* Member list */}
      {isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : error ? (
        <p className="text-sm text-destructive-foreground">Failed to load users</p>
      ) : !users || users.length === 0 ? (
        <p className="text-sm text-muted-foreground">No members found.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          {users.map((user, idx) => (
            <div
              key={user.id}
              className={[
                'flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-muted/30',
                !user.is_active ? 'opacity-60' : '',
                idx < users.length - 1 ? 'border-b border-border' : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              {/* Avatar */}
              <UserAvatar username={user.username} />

              {/* Name + email */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-medium text-foreground">{user.username}</span>
                  {isSelf(user) && (
                    <span className="text-xs text-muted-foreground">(you)</span>
                  )}
                </div>
                <span className="block truncate font-mono text-xs text-muted-foreground">
                  {user.email ?? '—'}
                </span>
              </div>

              {/* Role chip — real backend roles only: admin | user */}
              <Badge
                variant={user.role === 'admin' ? 'default' : 'secondary'}
                className={user.role === 'admin' ? 'bg-brand text-brand-foreground' : ''}
              >
                {user.role === 'admin' ? 'Admin' : 'User'}
              </Badge>

              {/* Last login */}
              <span className="w-20 shrink-0 text-right font-mono text-xs text-muted-foreground">
                {user.last_login_at ? formatRelativeTime(user.last_login_at) : 'Never'}
              </span>

              {/* Actions */}
              <div className="flex shrink-0 items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleToggleActive(user)}
                  disabled={isSelf(user) || pendingToggleId === user.id}
                  title={
                    isSelf(user)
                      ? 'Cannot deactivate your own account'
                      : user.is_active
                        ? 'Deactivate'
                        : 'Activate'
                  }
                >
                  {user.is_active ? 'Deactivate' : 'Activate'}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPasswordTarget(user)}
                >
                  Password
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDeleteTarget(user)}
                  disabled={isSelf(user)}
                  title={isSelf(user) ? 'Cannot delete your own account' : 'Delete'}
                  className="text-destructive hover:text-destructive"
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Invite / Create User Dialog */}
      <Dialog open={showCreate} onClose={closeCreateDialog} title="Invite Member">
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            placeholder="e.g., jsmith"
            autoFocus
            required
          />
          <Input
            label="Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Enter a password"
            required
          />
          <Select
            label="Role"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value as UserRole)}
            options={[
              { value: 'user', label: 'User' },
              { value: 'admin', label: 'Admin' },
            ]}
          />
          <Input
            label="Email (optional)"
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="e.g., jsmith@example.com"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={closeCreateDialog}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!newUsername.trim() || !newPassword.trim() || createUser.isPending}
            >
              {createUser.isPending ? 'Creating...' : 'Create User'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Change Password Dialog */}
      <Dialog
        open={passwordTarget !== null}
        onClose={closePasswordDialog}
        title={`Change Password — ${passwordTarget?.username ?? ''}`}
      >
        <form onSubmit={handleChangePassword} className="space-y-4">
          {passwordTarget && isSelf(passwordTarget) && (
            <Input
              label="Current Password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter your current password"
              autoFocus
              required
            />
          )}
          <Input
            label="New Password"
            type="password"
            value={newPasswordValue}
            onChange={(e) => setNewPasswordValue(e.target.value)}
            placeholder="Enter a new password"
            autoFocus={passwordTarget !== null && !isSelf(passwordTarget)}
            required
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={closePasswordDialog}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                !newPasswordValue.trim() ||
                (passwordTarget !== null &&
                  isSelf(passwordTarget) &&
                  !currentPassword.trim()) ||
                changePassword.isPending
              }
            >
              {changePassword.isPending ? 'Saving...' : 'Change Password'}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Member"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete{' '}
            <span className="font-medium text-foreground">{deleteTarget?.username}</span>? This
            action cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteUser.isPending}
            >
              {deleteUser.isPending ? 'Deleting...' : 'Delete Member'}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
