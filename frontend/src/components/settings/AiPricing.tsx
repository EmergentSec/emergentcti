import { useState, type FormEvent } from 'react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useDeleteAiPricingRow, useAiPricing, useSaveAiPricingRow } from '@/hooks/useAiUsage'
import { useToast } from '@/contexts/ToastContext'
import { aiRequestErrorMessage } from '@/lib/aiErrors'
import { AI_PROVIDERS, type AiProvider } from '@/types/ai'

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
          setModel('')
          setInputPrice('')
          setOutputPrice('')
        },
        onError: (err) => setFormError(aiRequestErrorMessage(err, "Couldn't save pricing.")),
      },
    )
  }

  const handleDelete = (p: AiProvider, m: string) => {
    del.mutate(
      { provider: p, model: m },
      {
        onSuccess: () => toast('Pricing row deleted', 'success'),
        onError: (err) => toast(aiRequestErrorMessage(err, "Couldn't delete pricing."), 'error'),
      },
    )
  }

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
            onChange={(e) => setProvider(e.target.value as AiProvider)}
            options={AI_PROVIDERS.map((p) => ({ value: p, label: p }))}
          />
          <Input id="ai-pricing-model" label="Model ID" value={model} onChange={(e) => setModel(e.target.value)} />
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
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Add / update'}
          </Button>
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
              {(data?.items ?? []).map((row) => (
                <TableRow key={`${row.provider}-${row.model}`}>
                  <TableCell>{row.provider}</TableCell>
                  <TableCell className="font-mono text-xs">{row.model}</TableCell>
                  <TableCell>{row.input_usd_per_mtok}</TableCell>
                  <TableCell>{row.output_usd_per_mtok}</TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      disabled={del.isPending}
                      onClick={() => handleDelete(row.provider, row.model)}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </Card>
  )
}
