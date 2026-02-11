import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useEnrichmentHistory, useProviders, useTriggerEnrichment } from '@/hooks/useEnrichment';
import { useToast } from '@/contexts/ToastContext';
import { formatRelativeTime } from '@/lib/utils';
import type { EnrichmentRunResponse } from '@/types/enrichment';

interface EnrichmentPanelProps {
  observableId: string;
  observableType: string;
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  running: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  success: 'bg-green-500/20 text-green-400 border-green-500/30',
  failure: 'bg-red-500/20 text-red-400 border-red-500/30',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant="outline" className={STATUS_STYLES[status] || ''}>
      {status}
    </Badge>
  );
}

function EnrichmentRunItem({ run }: { run: EnrichmentRunResponse }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md border border-border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status} />
          <span className="text-xs text-muted-foreground">
            {formatRelativeTime(run.created_at)}
          </span>
        </div>
        {(run.result_data || run.error_message) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            className="h-6 px-2 text-xs text-muted-foreground"
          >
            {expanded ? 'Collapse' : 'Details'}
          </Button>
        )}
      </div>

      {run.summary && (
        <p className="text-sm text-foreground">{run.summary}</p>
      )}

      {run.status === 'failure' && run.error_message && (
        <p className="text-sm text-red-400">{run.error_message}</p>
      )}

      {expanded && run.result_data && Object.keys(run.result_data).length > 0 && (
        <pre className="rounded-md bg-muted p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-64 overflow-y-auto">
          {JSON.stringify(run.result_data, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ProviderGroup({
  providerName,
  runs,
}: {
  providerName: string;
  runs: EnrichmentRunResponse[];
}) {
  const [showAll, setShowAll] = useState(false);
  const sortedRuns = [...runs].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
  const displayedRuns = showAll ? sortedRuns : sortedRuns.slice(0, 3);
  const hasMore = sortedRuns.length > 3;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-medium capitalize">{providerName}</h4>
        <Badge variant="secondary" className="tabular-nums">
          {runs.length}
        </Badge>
      </div>
      <div className="space-y-2">
        {displayedRuns.map((run) => (
          <EnrichmentRunItem key={run.id} run={run} />
        ))}
      </div>
      {hasMore && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowAll(!showAll)}
          className="text-xs text-muted-foreground"
        >
          {showAll ? 'Show less' : `Show ${sortedRuns.length - 3} more`}
        </Button>
      )}
    </div>
  );
}

export function EnrichmentPanel({ observableId, observableType }: EnrichmentPanelProps) {
  const { data: history = [], isLoading: historyLoading } = useEnrichmentHistory(observableId);
  const { data: providers = [] } = useProviders();
  const triggerMutation = useTriggerEnrichment();
  const { addToast } = useToast();

  // Filter providers that support this observable type and are enabled + configured
  const availableProviders = providers.filter(
    (p) => p.configured && p.enabled && p.supported_types.includes(observableType)
  );

  // Group runs by provider
  const groupedRuns: Record<string, EnrichmentRunResponse[]> = {};
  for (const run of history) {
    if (!groupedRuns[run.provider_name]) {
      groupedRuns[run.provider_name] = [];
    }
    groupedRuns[run.provider_name].push(run);
  }

  const providerNames = Object.keys(groupedRuns).sort();

  const handleEnrichAll = () => {
    triggerMutation.mutate(
      { observableId },
      {
        onSuccess: () => {
          addToast('Enrichment triggered for all providers', 'success');
        },
        onError: () => {
          addToast('Failed to trigger enrichment', 'error');
        },
      }
    );
  };

  const handleEnrichProvider = (providerName: string) => {
    triggerMutation.mutate(
      { observableId, providerName },
      {
        onSuccess: () => {
          addToast(`Enrichment triggered: ${providerName}`, 'success');
        },
        onError: () => {
          addToast(`Failed to trigger enrichment: ${providerName}`, 'error');
        },
      }
    );
  };

  const hasRunningEnrichment = history.some(
    (r) => r.status === 'pending' || r.status === 'running'
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            Enrichment
            {history.length > 0 && (
              <Badge variant="secondary" className="ml-2 tabular-nums">
                {history.length}
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            {availableProviders.length > 1 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleEnrichAll}
                disabled={triggerMutation.isPending || hasRunningEnrichment}
              >
                {triggerMutation.isPending ? 'Enriching...' : 'Enrich All'}
              </Button>
            )}
            {availableProviders.length === 1 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleEnrichProvider(availableProviders[0].name)}
                disabled={triggerMutation.isPending || hasRunningEnrichment}
              >
                {triggerMutation.isPending ? 'Enriching...' : 'Enrich'}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {historyLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="sm" />
          </div>
        ) : providerNames.length === 0 ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground italic py-4 text-center">
              No enrichment results yet.
            </p>
            {availableProviders.length > 0 && (
              <div className="flex flex-wrap gap-2 justify-center">
                {availableProviders.map((provider) => (
                  <Button
                    key={provider.name}
                    variant="outline"
                    size="sm"
                    onClick={() => handleEnrichProvider(provider.name)}
                    disabled={triggerMutation.isPending}
                  >
                    {provider.name}
                  </Button>
                ))}
              </div>
            )}
            {availableProviders.length === 0 && providers.length > 0 && (
              <p className="text-xs text-muted-foreground text-center">
                No configured providers support this observable type.
              </p>
            )}
            {providers.length === 0 && (
              <p className="text-xs text-muted-foreground text-center">
                No enrichment providers configured. Configure providers in Settings.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            {providerNames.map((name) => (
              <ProviderGroup
                key={name}
                providerName={name}
                runs={groupedRuns[name]}
              />
            ))}

            {/* Show buttons for providers that haven't been run yet */}
            {availableProviders.filter((p) => !groupedRuns[p.name]).length > 0 && (
              <div className="border-t border-border pt-4">
                <p className="text-xs text-muted-foreground mb-2">
                  Additional providers available:
                </p>
                <div className="flex flex-wrap gap-2">
                  {availableProviders
                    .filter((p) => !groupedRuns[p.name])
                    .map((provider) => (
                      <Button
                        key={provider.name}
                        variant="outline"
                        size="sm"
                        onClick={() => handleEnrichProvider(provider.name)}
                        disabled={triggerMutation.isPending}
                      >
                        {provider.name}
                      </Button>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
