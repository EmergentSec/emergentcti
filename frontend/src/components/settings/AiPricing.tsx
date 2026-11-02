import { useState, type FormEvent } from 'react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useDeleteAiPricingRow, useAiPricing, useSaveAiPricingRow } from '@/hooks/useAiUsage'
import { useToast } from '@/contexts/ToastContext'
import { aiRequestErrorMessage } from '@/lib/aiErrors'
import { AI_PROVIDERS, type AiModelPricingRow, type AiProvider } from '@/types/ai'

export function AiPricingTable() {
  const { toast } = useToast()
  const { data, isLoading, error } = useAiPricing()
  const save = useSaveAiPricingRow()
  const del = useDeleteAiPricingRow()

  const [provider, setProvider] = useState<AiProvider>('anthropic')
  const [model, setModel] = useState('')
  const [inputPrice, setInputPrice] = useState('')
  const [outputPrice, setOutputPrice] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [editing, setEditing] = useState<{ provider: AiProvider; model: string } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<AiModelPricingRow | null>(null)

  const resetForm = () => {
    setEditing(null)
    setModel('')
    setInputPrice('')
    setOutputPrice('')
    setFormError(null)
  }

  const startEdit = (row: AiModelPricingRow) => {
    setEditing({ provider: row.provider, model: row.model })
    setProvider(row.provider)
    setModel(row.model)
    setInputPrice(row.input_usd_per_mtok)
    setOutputPrice(row.output_usd_per_mtok)
    setFormError(null)
  }

  const handleAdd = (e: FormEvent) => {
    e.preventDefault()
    const modelTrim = model.trim()
    if (!modelTrim) {
      setFormError('Model ID is required.')
      return
    }
    if (!/^\d+(\.\d{1,6})?$/.test(inputPrice.trim()) || !/^\d+(\.\d{1,6})?$/.test(outputPrice.trim())) {
      setFormError('Prices must be non-negative decimals with up to six places.')
      return
    }
    setFormError(null)
    save.mutate(
      {
        provider,
        model: modelTrim,
        input_usd_per_mtok: inputPrice.trim(),
        output_usd_per_mtok: outputPrice.trim(),
      },
      {
        onSuccess: () => {
          toast('Pricing row saved', 'success')
          resetForm()
        },
        onError: (err) => setFormError(aiRequestErrorMessage(err, "Couldn't save pricing.")),
      },
    )
  }

  const confirmDelete = () => {
    if (!deleteTarget || del.isPending) return
    const { provider: p, model: m } = deleteTarget
    del.mutate(
      { provider: p, model: m },
      {
        onSuccess: () => {
          setDeleteTarget(null)
          if (editing && editing.provider === p && editing.model === m) resetForm()
          toast('Pricing row deleted', 'success')
        },
        onError: (err) => {
          setDeleteTarget(null)
          toast(aiRequestErrorMessage(err, "Couldn't delete pricing."), 'error')
        },
      },
    )
  }

  const items = data?.items ?? []

  return (
    <Card>
      <section aria-labelledby="ai-pricing-title" className="space-y-4 p-5">
        <div>
          <h3 id="ai-pricing-title" className="text-base font-semibold text-foreground">
            Model pricing
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Admin-entered USD per million tokens. Used for local cost estimates only.
          </p>
        </div>

        <form onSubmit={handleAdd} className="grid gap-3 sm:grid-cols-[10rem_1fr_8rem_8rem_auto] sm:items-end">
          <Select
            id="ai-pricing-provider"
            label="Provider"
            value={provider}
            disabled={editing !== null}
            onChange={(e) => setProvider(e.target.value as AiProvider)}
            options={AI_PROVIDERS.map((p) => ({ value: p, label: p }))}
          />
          <Input
            id="ai-pricing-model"
            label="Model ID"
            value={model}
            readOnly={editing !== null}
            onChange={(e) => setModel(e.target.value)}
          />
          <Input
            id="ai-pricing-in"
            label="Input $/Mtok"
            value={inputPrice}
            onChange={(e) => setInputPrice(e.target.value)}
            inputMode="decimal"
          />
          <Input
            id="ai-pricing-out"
            label="Output $/Mtok"
            value={outputPrice}
            onChange={(e) => setOutputPrice(e.target.value)}
            inputMode="decimal"
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : editing ? 'Save changes' : 'Add / update'}
            </Button>
            {editing && (
              <Button type="button" variant="outline" onClick={resetForm}>
                Cancel edit
              </Button>
            )}
          </div>
        </form>
        {formError && (
          <p role="alert" className="text-sm text-destructive">
            {formError}
          </p>
        )}

        {isLoading ? (
          <LoadingSpinner />
        ) : error ? (
          <p className="text-sm text-destructive">{aiRequestErrorMessage(error, "Couldn't load pricing.")}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Input $/Mtok</TableHead>
                <TableHead>Output $/Mtok</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-sm text-muted-foreground">
                    No pricing rows yet. Unpriced models follow the unpriced-model policy above.
                  </TableCell>
                </TableRow>
              ) : (
                items.map((row) => (
                  <TableRow key={`${row.provider}-${row.model}`}>
                    <TableCell>{row.provider}</TableCell>
                    <TableCell className="font-mono text-xs">{row.model}</TableCell>
                    <TableCell>{row.input_usd_per_mtok}</TableCell>
                    <TableCell>{row.output_usd_per_mtok}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          aria-label={`Edit pricing for ${row.provider}/${row.model}`}
                          onClick={() => startEdit(row)}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          aria-label={`Delete pricing for ${row.provider}/${row.model}`}
                          disabled={del.isPending}
                          onClick={() => setDeleteTarget(row)}
                        >
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </section>

      <Dialog open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} title="Delete pricing row?">
        <div className="space-y-4 text-sm">
          <p className="text-muted-foreground">
            Delete local pricing for{' '}
            <code className="break-all font-mono text-xs text-foreground">
              {deleteTarget ? `${deleteTarget.provider}/${deleteTarget.model}` : ''}
            </code>
            ? Its costs become unknown, and if the unpriced-model policy is “Block”, inference tests for this model
            will be blocked.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={del.isPending}>
              {del.isPending ? 'Deleting…' : 'Delete pricing'}
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  )
}
