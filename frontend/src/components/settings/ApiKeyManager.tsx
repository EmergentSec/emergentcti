import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApiKeys, createApiKey, revokeApiKey } from '@/api/settings'
import { useToast } from '@/contexts/ToastContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { formatDate } from '@/lib/utils'
import type { ApiKeyCreateResponse } from '@/types/auth'

export function ApiKeyManager() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyDescription, setNewKeyDescription] = useState('')
  const [createdKey, setCreatedKey] = useState<ApiKeyCreateResponse | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: keys, isLoading, error } = useQuery({
    queryKey: ['apiKeys'],
    queryFn: getApiKeys,
  })

  const createMutation = useMutation({
    mutationFn: createApiKey,
    onSuccess: (data) => {
      setCreatedKey(data)
      setNewKeyName('')
      setNewKeyDescription('')
      queryClient.invalidateQueries({ queryKey: ['apiKeys'] })
      toast('API key created', 'success')
    },
    onError: () => {
      toast('Failed to create API key', 'error')
    },
  })

  const revokeMutation = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['apiKeys'] })
      toast('API key revoked', 'success')
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : 'Failed to revoke key'
      toast(message, 'error')
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newKeyName.trim()) return
    createMutation.mutate({
      name: newKeyName.trim(),
      description: newKeyDescription.trim() || undefined,
    })
  }

  const handleCopy = async () => {
    if (!createdKey) return
    try {
      await navigator.clipboard.writeText(createdKey.key)
      setCopied(true)
      toast('API key copied to clipboard', 'success')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast('Failed to copy to clipboard', 'error')
    }
  }

  const closeCreateDialog = () => {
    setShowCreate(false)
    setCreatedKey(null)
    setNewKeyName('')
    setNewKeyDescription('')
    setCopied(false)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>API Keys</CardTitle>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            Create New Key
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <p className="text-sm text-destructive-foreground">Failed to load API keys</p>
        ) : !keys || keys.length === 0 ? (
          <p className="text-sm text-muted-foreground">No API keys found</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Prefix</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.map((key) => (
                <TableRow key={key.id}>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {key.key_prefix}...
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium">{key.name}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(key.created_at)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {key.last_used_at ? formatDate(key.last_used_at) : 'Never'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => {
                        if (confirm('Are you sure you want to revoke this API key?')) {
                          revokeMutation.mutate(key.id)
                        }
                      }}
                      disabled={revokeMutation.isPending}
                    >
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {/* Create API Key Dialog */}
        <Dialog
          open={showCreate}
          onClose={closeCreateDialog}
          title={createdKey ? 'API Key Created' : 'Create New API Key'}
        >
          {createdKey ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-amber-500/30 bg-amber-950/30 p-4">
                <p className="mb-2 text-sm font-medium text-amber-200">
                  Save this key now. You will not be able to see it again.
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded bg-background px-3 py-2 font-mono text-sm text-foreground break-all">
                    {createdKey.key}
                  </code>
                  <Button size="sm" variant="outline" onClick={handleCopy}>
                    {copied ? 'Copied' : 'Copy'}
                  </Button>
                </div>
              </div>
              <div className="flex justify-end">
                <Button onClick={closeCreateDialog}>Done</Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleCreate} className="space-y-4">
              <Input
                label="Key Name"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="e.g., Production Server"
                autoFocus
              />
              <Input
                label="Description (optional)"
                value={newKeyDescription}
                onChange={(e) => setNewKeyDescription(e.target.value)}
                placeholder="What is this key used for?"
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
                  disabled={!newKeyName.trim() || createMutation.isPending}
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Key'}
                </Button>
              </div>
            </form>
          )}
        </Dialog>
      </CardContent>
    </Card>
  )
}
