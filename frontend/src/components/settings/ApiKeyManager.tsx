import { useState } from 'react'
import { X } from '@phosphor-icons/react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApiKeys, createApiKey, revokeApiKey } from '@/api/settings'
import { useToast } from '@/contexts/ToastContext'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Dialog } from '@/components/ui/Dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { Card } from '@/components/ui/Card'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import type { ApiKeyCreateResponse } from '@/types/auth'

export function ApiKeyManager() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyDescription, setNewKeyDescription] = useState('')
  const [createdKey, setCreatedKey] = useState<ApiKeyCreateResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null)

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
      setRevokeTarget(null)
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : 'Failed to revoke key'
      toast(message, 'error')
      setRevokeTarget(null)
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
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-foreground">API keys</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Authenticate requests with the{' '}
            <code className="rounded bg-surface2 px-1 py-0.5 font-mono text-xs">X-API-Key</code>{' '}
            header
          </p>
        </div>
        <Button variant="brand" onClick={() => setShowCreate(true)}>
          Create key
        </Button>
      </div>

      {/* Terminal curl example */}
      <div className="overflow-hidden rounded-xl border border-border bg-surface2">
        <div className="flex items-center gap-2 border-b border-border bg-surface3 px-4 py-2">
          <span className="font-mono text-xs text-muted-foreground">$_</span>
        </div>
        <pre className="overflow-x-auto px-4 py-3 font-mono text-sm text-foreground">
          {'curl -H "X-API-Key: cti_••••••••" https://<your-instance>/api/v1/observables'}
        </pre>
      </div>

      {/* Keys table */}
      {isLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">Failed to load API keys</p>
      ) : !keys || keys.length === 0 ? (
        <Card>
          <EmptyState
            title="No API keys found"
            description="Create a key to authenticate API requests."
          >
            <Button onClick={() => setShowCreate(true)}>Create key</Button>
          </EmptyState>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <Table className="min-w-[680px]">
          <TableHeader>
            <TableRow>
              <TableHead>NAME</TableHead>
              <TableHead>KEY</TableHead>
              <TableHead>CREATED</TableHead>
              <TableHead>LAST USED</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {keys.map((key) => (
              <TableRow key={key.id}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{key.name}</span>
                    {key.name === 'Default Admin Key' && (
                      <span className="text-xs text-muted-foreground">
                        auto-generated on first startup
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <code className="rounded bg-surface2 px-2 py-0.5 font-mono text-xs text-muted-foreground">
                    {key.key_prefix}
                  </code>
                </TableCell>
                <TableCell className="font-mono text-sm text-muted-foreground">
                  {formatDate(key.created_at)}
                </TableCell>
                <TableCell className="font-mono text-sm text-muted-foreground">
                  {key.last_used_at ? formatRelativeTime(key.last_used_at) : 'Never'}
                </TableCell>
                <TableCell>
                  <button
                    className="rounded p-1 text-muted-foreground transition-colors hover:text-destructive"
                    onClick={() => setRevokeTarget(key.id)}
                    title="Revoke key"
                    aria-label={`Revoke key ${key.name}`}
                  >
                    <X size={15} aria-hidden="true" />
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
          </Table>
        </Card>
      )}

      {/* Create API Key Dialog */}
      <Dialog
        open={showCreate}
        onClose={closeCreateDialog}
        title={createdKey ? 'API Key Created' : 'Create New API Key'}
      >
        {createdKey ? (
          <div className="space-y-4">
            <div
              className="rounded-xl border border-warning bg-warning-soft p-4"
            >
              <p className="mb-2 text-sm font-medium text-warning-ink">
                Save this key now — you will not be able to see it again.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <code className="flex-1 break-all rounded bg-surface2 px-3 py-2 font-mono text-sm text-foreground">
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
              <Button type="button" variant="outline" onClick={closeCreateDialog}>
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

      {/* Revoke Confirm Dialog */}
      <Dialog
        open={revokeTarget !== null}
        onClose={() => setRevokeTarget(null)}
        title="Revoke API Key"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Are you sure you want to revoke this key? Any integrations using it will immediately
            lose access.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setRevokeTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => revokeTarget && revokeMutation.mutate(revokeTarget)}
              disabled={revokeMutation.isPending}
            >
              {revokeMutation.isPending ? 'Revoking...' : 'Revoke Key'}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
