import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useHeatmap, useSyncAttackData } from '@/hooks/useAttack';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/contexts/ToastContext';
import { isAdmin } from '@/lib/permissions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import type { HeatmapCell, TacticResponse } from '@/types/attack';

function getHeatColor(count: number, maxCount: number): string {
  if (count === 0) return 'bg-muted/50 text-muted-foreground';
  if (maxCount === 0) return 'bg-muted/50 text-muted-foreground';

  const ratio = count / maxCount;

  if (ratio <= 0.2) return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
  if (ratio <= 0.4) return 'bg-orange-500/20 text-orange-300 border-orange-500/30';
  if (ratio <= 0.6) return 'bg-orange-600/30 text-orange-200 border-orange-600/40';
  if (ratio <= 0.8) return 'bg-red-500/30 text-red-300 border-red-500/40';
  return 'bg-red-600/40 text-red-200 border-red-600/50';
}

interface CellDetailProps {
  cell: HeatmapCell;
  tactic: TacticResponse;
  onClose: () => void;
}

function CellDetail({ cell, tactic, onClose }: CellDetailProps) {
  const navigate = useNavigate();

  return (
    <Card className="absolute z-50 w-80 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">{cell.technique_name}</CardTitle>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors p-1"
            aria-label="Close detail"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <Badge variant="outline">{cell.technique_external_id}</Badge>
          <Badge variant="secondary">{tactic.name}</Badge>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            Linked Observables
          </p>
          <p className="text-2xl font-bold tabular-nums">{cell.count}</p>
        </div>
        {cell.count > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => {
              navigate(`/search?q=${encodeURIComponent(cell.technique_external_id)}`);
              onClose();
            }}
          >
            View Linked Observables
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export function AttackMatrixPage() {
  const { user } = useAuth();
  const { addToast } = useToast();
  const { data: heatmap, isLoading, error } = useHeatmap();
  const syncMutation = useSyncAttackData();

  const [selectedCell, setSelectedCell] = useState<{
    cell: HeatmapCell;
    tactic: TacticResponse;
  } | null>(null);

  const handleSync = () => {
    syncMutation.mutate(undefined, {
      onSuccess: () => {
        addToast('ATT&CK data sync started', 'success');
      },
      onError: () => {
        addToast('Failed to sync ATT&CK data', 'error');
      },
    });
  };

  // Build the matrix: organize cells by tactic
  const { tacticColumns, maxCount } = useMemo(() => {
    if (!heatmap) return { tacticColumns: [], maxCount: 0 };

    const sortedTactics = [...heatmap.tactics].sort((a, b) => a.order - b.order);

    // Group cells by tactic_id
    const cellsByTactic = new Map<string, HeatmapCell[]>();
    for (const tactic of sortedTactics) {
      cellsByTactic.set(tactic.id, []);
    }
    for (const cell of heatmap.cells) {
      const existing = cellsByTactic.get(cell.tactic_id);
      if (existing) {
        existing.push(cell);
      }
    }

    // Sort techniques within each tactic by external_id
    for (const cells of cellsByTactic.values()) {
      cells.sort((a, b) => a.technique_external_id.localeCompare(b.technique_external_id));
    }

    let max = 0;
    for (const cell of heatmap.cells) {
      if (cell.count > max) max = cell.count;
    }

    const columns = sortedTactics.map((tactic) => ({
      tactic,
      cells: cellsByTactic.get(tactic.id) || [],
    }));

    return { tacticColumns: columns, maxCount: max };
  }, [heatmap]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg text-muted-foreground">
          Failed to load ATT&CK matrix data
        </p>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">MITRE ATT&CK Matrix</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Technique coverage heatmap based on linked observables
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Legend */}
          <div className="hidden md:flex items-center gap-2 text-xs text-muted-foreground">
            <span>Coverage:</span>
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded-sm bg-muted/50 border border-border" />
              <span>0</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded-sm bg-yellow-500/20 border border-yellow-500/30" />
              <span>Low</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded-sm bg-orange-500/20 border border-orange-500/30" />
              <span>Med</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded-sm bg-red-600/40 border border-red-600/50" />
              <span>High</span>
            </div>
          </div>
          {isAdmin(user) && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSync}
              disabled={syncMutation.isPending}
            >
              {syncMutation.isPending ? 'Syncing...' : 'Sync ATT&CK Data'}
            </Button>
          )}
        </div>
      </div>

      {/* Matrix */}
      {tacticColumns.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
            <p className="text-muted-foreground">
              No ATT&CK data available.
            </p>
            {isAdmin(user) && (
              <Button
                variant="outline"
                onClick={handleSync}
                disabled={syncMutation.isPending}
              >
                {syncMutation.isPending ? 'Syncing...' : 'Sync ATT&CK Data'}
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="overflow-x-auto pb-4">
          <div
            className="grid gap-2"
            style={{
              gridTemplateColumns: `repeat(${tacticColumns.length}, minmax(160px, 1fr))`,
            }}
          >
            {/* Tactic headers */}
            {tacticColumns.map(({ tactic }) => (
              <div
                key={tactic.id}
                className="rounded-lg border bg-card p-3 text-center"
              >
                <p className="text-xs font-bold text-primary uppercase tracking-wider">
                  {tactic.external_id}
                </p>
                <p className="text-xs font-medium mt-1 line-clamp-2">
                  {tactic.name}
                </p>
              </div>
            ))}

            {/* Technique cells per tactic column */}
            {tacticColumns.map(({ tactic, cells }) => (
              <div key={`col-${tactic.id}`} className="space-y-1">
                {cells.length === 0 ? (
                  <div className="rounded-md border border-dashed border-border p-3 text-center">
                    <p className="text-xs text-muted-foreground italic">
                      No techniques
                    </p>
                  </div>
                ) : (
                  cells.map((cell) => (
                    <div key={cell.technique_id} className="relative">
                      <button
                        onClick={() =>
                          setSelectedCell(
                            selectedCell?.cell.technique_id === cell.technique_id &&
                              selectedCell?.tactic.id === tactic.id
                              ? null
                              : { cell, tactic }
                          )
                        }
                        className={`w-full rounded-md border p-2 text-left transition-all hover:ring-1 hover:ring-ring ${getHeatColor(
                          cell.count,
                          maxCount
                        )}`}
                        aria-label={`${cell.technique_name} (${cell.technique_external_id}): ${cell.count} observables`}
                      >
                        <p className="text-[10px] font-mono opacity-70">
                          {cell.technique_external_id}
                        </p>
                        <p className="text-xs font-medium leading-tight line-clamp-2">
                          {cell.technique_name}
                        </p>
                        {cell.count > 0 && (
                          <p className="text-[10px] font-bold mt-1 tabular-nums">
                            {cell.count}
                          </p>
                        )}
                      </button>
                      {selectedCell?.cell.technique_id === cell.technique_id &&
                        selectedCell?.tactic.id === tactic.id && (
                          <div className="absolute left-0 top-full mt-1 z-50">
                            <CellDetail
                              cell={cell}
                              tactic={tactic}
                              onClose={() => setSelectedCell(null)}
                            />
                          </div>
                        )}
                    </div>
                  ))
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary stats */}
      {heatmap && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Tactics
              </p>
              <p className="text-2xl font-bold tabular-nums mt-1">
                {heatmap.tactics.length}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Techniques
              </p>
              <p className="text-2xl font-bold tabular-nums mt-1">
                {new Set(heatmap.cells.map((c) => c.technique_id)).size}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Covered Techniques
              </p>
              <p className="text-2xl font-bold tabular-nums mt-1">
                {new Set(
                  heatmap.cells
                    .filter((c) => c.count > 0)
                    .map((c) => c.technique_id)
                ).size}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Total Mappings
              </p>
              <p className="text-2xl font-bold tabular-nums mt-1">
                {heatmap.cells.reduce((sum, c) => sum + c.count, 0)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
