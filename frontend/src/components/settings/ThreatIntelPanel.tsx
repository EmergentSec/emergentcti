import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useToast } from '@/contexts/ToastContext'
import {
  fetchThreatIntelFeeds,
  generateThreatIntelReport,
  listThreatIntelSkills,
  type FeedFetchResponse,
} from '@/api/threatIntel'
import { aiRequestErrorMessage } from '@/lib/aiErrors'

export function ThreatIntelPanel() {
  const { toast } = useToast()
  const [lastFetch, setLastFetch] = useState<FeedFetchResponse | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)

  const skills = useQuery({
    queryKey: ['threat-intel-skills'],
    queryFn: listThreatIntelSkills,
  })

  const fetchFeeds = useMutation({
    mutationFn: fetchThreatIntelFeeds,
    onSuccess: (data) => {
      setLastFetch(data)
      setSelectedIndex(0)
      toast(`Fetched ${data.total_items} new feed item${data.total_items === 1 ? '' : 's'}`, 'success')
    },
    onError: (err) => toast(aiRequestErrorMessage(err, "Couldn't fetch threat feeds."), 'error'),
  })

  const generate = useMutation({
    mutationFn: (item: Record<string, unknown>) => generateThreatIntelReport(item),
    onSuccess: (data) => {
      toast(`Report saved: ${data.title}`, 'success')
    },
    onError: (err) => toast(aiRequestErrorMessage(err, "Couldn't generate the report."), 'error'),
  })

  const items = lastFetch?.items ?? []
  const selected = items[selectedIndex]

  return (
    <Card>
      <section aria-labelledby="threat-intel-title" className="space-y-4 p-5">
        <div>
          <h3 id="threat-intel-title" className="text-base font-semibold text-foreground">
            Threat intel pipeline
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Fetch open-source feeds, then run the research model and writer model to produce a report.
            Configure research and writer models above first.
          </p>
        </div>

        {skills.isLoading ? (
          <LoadingSpinner />
        ) : skills.data ? (
          <p className="text-sm text-muted-foreground">
            Skills loaded: {skills.data.map((s) => s.title).join(' · ')}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => fetchFeeds.mutate()} disabled={fetchFeeds.isPending}>
            {fetchFeeds.isPending ? 'Fetching…' : 'Fetch feeds'}
          </Button>
          <Button
            variant="outline"
            disabled={!selected || generate.isPending}
            onClick={() => selected && generate.mutate(selected)}
          >
            {generate.isPending ? 'Generating…' : 'Generate report for selected item'}
          </Button>
        </div>

        {lastFetch && (
          <div className="space-y-3">
            <p className="text-sm text-foreground">
              Last fetch: <span className="font-medium">{lastFetch.total_items}</span> items
              {lastFetch.timestamp ? ` · ${lastFetch.timestamp}` : ''}
            </p>
            {items.length === 0 ? (
              <p className="text-sm text-muted-foreground">No new items since the last run.</p>
            ) : (
              <label className="block space-y-1.5 text-sm">
                <span className="text-muted-foreground">Select an item for a deep-dive</span>
                <select
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
                  value={selectedIndex}
                  onChange={(e) => setSelectedIndex(Number(e.target.value))}
                >
                  {items.map((item, index) => {
                    const title = String(item.title ?? item.cve_id ?? `Item ${index + 1}`)
                    const severity = item.severity ? ` [${String(item.severity)}]` : ''
                    return (
                      <option key={`${item.link ?? title}-${index}`} value={index}>
                        {title}
                        {severity}
                      </option>
                    )
                  })}
                </select>
              </label>
            )}
            {generate.data && (
              <p className="text-sm text-success-ink">
                Created report <code className="font-mono text-xs">{generate.data.report_id}</code>
                {' · '}
                {generate.data.writer_provider}/{generate.data.writer_model}
              </p>
            )}
          </div>
        )}
      </section>
    </Card>
  )
}
