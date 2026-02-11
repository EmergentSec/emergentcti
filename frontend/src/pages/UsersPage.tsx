import { useState, type FormEvent } from 'react';
import { Navigate } from 'react-router-dom';
import { useUsers, useRegisterUser, useAuth, useUpdateUser, useDeleteUser, useBulkUpdateUsers, useBulkDeleteUsers } from '@/hooks/useAuth';
import { canManageUsers } from '@/lib/permissions';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { formatDate } from '@/lib/utils';

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const { data: users, isLoading } = useUsers();
  const registerMutation = useRegisterUser();
  const updateUserMutation = useUpdateUser();
  const deleteUserMutation = useDeleteUser();
  const bulkUpdateMutation = useBulkUpdateUsers();
  const bulkDeleteMutation = useBulkDeleteUsers();
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());

  const toggleUserSelect = (id: string) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleUserSelectAll = () => {
    if (!users) return;
    setSelectedUserIds((prev) => {
      const allSelected = users.every((u) => prev.has(u.id));
      if (allSelected) return new Set();
      return new Set(users.map((u) => u.id));
    });
  };

  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  // Form state
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<'admin' | 'analyst' | 'readonly'>('readonly');
  const [formError, setFormError] = useState('');

  if (!canManageUsers(currentUser)) {
    return <Navigate to="/" replace />;
  }

  const resetForm = () => {
    setNewUsername('');
    setNewEmail('');
    setNewPassword('');
    setNewRole('readonly');
    setFormError('');
  };

  const handleCreateSubmit = (e: FormEvent) => {
    e.preventDefault();
    setFormError('');
    registerMutation.mutate(
      {
        username: newUsername,
        email: newEmail,
        password: newPassword,
        role: newRole,
      },
      {
        onSuccess: () => {
          setCreateDialogOpen(false);
          resetForm();
        },
        onError: (error: unknown) => {
          let message = 'Failed to create user';
          if (error && typeof error === 'object' && 'response' in error) {
            const axiosError = error as { response?: { data?: { detail?: string | Array<{ msg: string }> } } };
            const detail = axiosError.response?.data?.detail;
            if (typeof detail === 'string') {
              message = detail;
            } else if (Array.isArray(detail)) {
              message = detail.map((d) => d.msg).join('; ');
            }
          } else if (error instanceof Error) {
            message = error.message;
          }
          setFormError(message);
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground">
            {users
              ? `${users.length} user${users.length !== 1 ? 's' : ''} registered`
              : 'Loading...'}
          </p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)}>
          + Create User
        </Button>
      </div>

      {selectedUserIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-3">
          <span className="text-sm font-medium">{selectedUserIds.size} selected</span>
          <div className="h-4 w-px bg-border" />
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              bulkUpdateMutation.mutate(
                { ids: Array.from(selectedUserIds), updates: { is_active: true } },
                { onSuccess: () => setSelectedUserIds(new Set()) }
              );
            }}
          >
            Activate
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              bulkUpdateMutation.mutate(
                { ids: Array.from(selectedUserIds), updates: { is_active: false } },
                { onSuccess: () => setSelectedUserIds(new Set()) }
              );
            }}
          >
            Deactivate
          </Button>
          <Select
            className="w-36 h-8 text-xs"
            value=""
            onChange={(e) => {
              if (e.target.value) {
                bulkUpdateMutation.mutate(
                  { ids: Array.from(selectedUserIds), updates: { role: e.target.value } },
                  { onSuccess: () => setSelectedUserIds(new Set()) }
                );
              }
            }}
          >
            <option value="">Change Role...</option>
            <option value="readonly">Readonly</option>
            <option value="analyst">Analyst</option>
            <option value="admin">Admin</option>
          </Select>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => {
              if (window.confirm(`Delete ${selectedUserIds.size} users?`)) {
                bulkDeleteMutation.mutate(Array.from(selectedUserIds), {
                  onSuccess: () => setSelectedUserIds(new Set()),
                });
              }
            }}
          >
            Delete Selected
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelectedUserIds(new Set())}>
            Clear
          </Button>
        </div>
      )}

      {/* Users Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-input bg-background"
                  checked={!!users && users.length > 0 && users.every((u) => selectedUserIds.has(u.id))}
                  onChange={toggleUserSelectAll}
                />
              </TableHead>
              <TableHead>Username</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>API Key</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                  Loading users...
                </TableCell>
              </TableRow>
            ) : users && users.length > 0 ? (
              users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-input bg-background"
                      checked={selectedUserIds.has(user.id)}
                      onChange={() => toggleUserSelect(user.id)}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell className="text-muted-foreground">{user.email}</TableCell>
                  <TableCell>
                    <Badge
                      variant="secondary"
                      className={
                        user.role === 'admin'
                          ? 'bg-red-500/20 text-red-400 border-red-500/30'
                          : user.role === 'analyst'
                            ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                            : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
                      }
                    >
                      {user.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div
                        className={`h-2 w-2 rounded-full ${
                          user.is_active ? 'bg-green-500' : 'bg-red-500'
                        }`}
                      />
                      <span className="text-sm">
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {user.has_api_key ? (
                      <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                        Active
                      </Badge>
                    ) : (
                      <Badge variant="secondary">None</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Select
                        className="w-28 h-7 text-xs"
                        value={user.role}
                        onChange={(e) => {
                          updateUserMutation.mutate({
                            userId: user.id,
                            data: { role: e.target.value },
                          });
                        }}
                      >
                        <option value="readonly">Readonly</option>
                        <option value="analyst">Analyst</option>
                        <option value="admin">Admin</option>
                      </Select>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={() => {
                          updateUserMutation.mutate({
                            userId: user.id,
                            data: { is_active: !user.is_active },
                          });
                        }}
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs text-red-400 hover:text-red-300"
                        onClick={() => {
                          if (window.confirm(`Delete user "${user.username}"?`)) {
                            deleteUserMutation.mutate(user.id);
                          }
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                  No users found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create User Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogClose onClose={() => { setCreateDialogOpen(false); resetForm(); }} />
          <DialogHeader>
            <DialogTitle>Create User</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="user-username" className="text-sm font-medium">
                Username
              </label>
              <Input
                id="user-username"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="johndoe"
                required
                minLength={3}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="user-email" className="text-sm font-medium">
                Email
              </label>
              <Input
                id="user-email"
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="john@example.com"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="user-password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="user-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                required
                minLength={8}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="user-role" className="text-sm font-medium">
                Role
              </label>
              <Select
                id="user-role"
                value={newRole}
                onChange={(e) =>
                  setNewRole(e.target.value as 'admin' | 'analyst' | 'readonly')
                }
              >
                <option value="readonly">Readonly</option>
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </Select>
            </div>

            {formError && (
              <p className="text-sm text-red-400">{formError}</p>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => { setCreateDialogOpen(false); resetForm(); }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={registerMutation.isPending}>
                {registerMutation.isPending ? 'Creating...' : 'Create User'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
