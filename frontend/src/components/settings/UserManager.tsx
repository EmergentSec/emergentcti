import { useState } from 'react'
import { useUsers, useCreateUser, useUpdateUser, useDeleteUser, useChangePassword } from '@/hooks/useUsers'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { formatRelativeTime, formatDate } from '@/lib/utils'
import type { User, UserRole } from '@/types/user'

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

  // Delete confirmation dialog state
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null)

  // Per-row pending state for toggle to avoid disabling all rows
  const [pendingToggleId, setPendingToggleId] = useState<string | null>(null)

  const isSelf = (user: User) => currentUser?.id === user.id

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
      }
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
      }
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
      }
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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Users</CardTitle>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            Add User
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <p className="text-sm text-destructive-foreground">Failed to load users</p>
        ) : !users || users.length === 0 ? (
          <p className="text-sm text-muted-foreground">No users found</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Username</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">
                    {user.username}
                    {isSelf(user) && (
                      <span className="ml-1.5 text-xs text-muted-foreground">(you)</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                      {user.role === 'admin' ? 'Admin' : 'User'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? 'success' : 'destructive'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.last_login_at ? formatRelativeTime(user.last_login_at) : 'Never'}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggleActive(user)}
                        disabled={isSelf(user) || pendingToggleId === user.id}
                        title={isSelf(user) ? 'Cannot deactivate your own account' : undefined}
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPasswordTarget(user)}
                      >
                        Password
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => setDeleteTarget(user)}
                        disabled={isSelf(user)}
                        title={isSelf(user) ? 'Cannot delete your own account' : undefined}
                      >
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {/* Create User Dialog */}
        <Dialog
          open={showCreate}
          onClose={closeCreateDialog}
          title="Add User"
        >
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
              <Button
                type="button"
                variant="outline"
                onClick={closeCreateDialog}
              >
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
              <Button
                type="button"
                variant="outline"
                onClick={closePasswordDialog}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={
                  !newPasswordValue.trim() ||
                  (passwordTarget !== null && isSelf(passwordTarget) && !currentPassword.trim()) ||
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
          title="Delete User"
        >
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to delete{' '}
              <span className="font-medium text-foreground">{deleteTarget?.username}</span>? This
              action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleteUser.isPending}
              >
                {deleteUser.isPending ? 'Deleting...' : 'Delete User'}
              </Button>
            </div>
          </div>
        </Dialog>
      </CardContent>
    </Card>
  )
}
