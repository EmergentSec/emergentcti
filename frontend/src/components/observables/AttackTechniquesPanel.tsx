import { useState, useMemo } from 'react';
import {
  useObservableTechniques,
  useTechniques,
  useMapTechnique,
  useUnmapTechnique,
} from '@/hooks/useAttack';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/contexts/ToastContext';
import { canEdit } from '@/lib/permissions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { formatRelativeTime } from '@/lib/utils';
import type { TechniqueResponse } from '@/types/attack';

interface AttackTechniquesPanelProps {
  observableId: string;
}

export function AttackTechniquesPanel({ observableId }: AttackTechniquesPanelProps) {
  const { user } = useAuth();
  const { addToast } = useToast();
  const {
    data: mappedTechniques = [],
    isLoading,
  } = useObservableTechniques(observableId);
  const mapMutation = useMapTechnique();
  const unmapMutation = useUnmapTechnique();

  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Load all techniques for the add modal
  const { data: allTechniques = [], isLoading: techniquesLoading } = useTechniques();

  // Filter techniques that are not already mapped
  const availableTechniques = useMemo(() => {
    const mappedIds = new Set(mappedTechniques.map((t) => t.technique_id));
    return allTechniques.filter((t) => !mappedIds.has(t.id));
  }, [allTechniques, mappedTechniques]);

  // Apply search filter
  const filteredTechniques = useMemo(() => {
    if (!searchQuery.trim()) return availableTechniques;
    const query = searchQuery.toLowerCase();
    return availableTechniques.filter(
      (t) =>
        t.name.toLowerCase().includes(query) ||
        t.external_id.toLowerCase().includes(query)
    );
  }, [availableTechniques, searchQuery]);

  const handleMap = (technique: TechniqueResponse) => {
    mapMutation.mutate(
      { observableId, techniqueId: technique.id },
      {
        onSuccess: () => {
          addToast(`Mapped ${technique.external_id} - ${technique.name}`, 'success');
        },
        onError: () => {
          addToast(`Failed to map technique`, 'error');
        },
      }
    );
  };

  const handleUnmap = (techniqueId: string, techniqueName: string) => {
    unmapMutation.mutate(
      { observableId, techniqueId },
      {
        onSuccess: () => {
          addToast(`Removed ${techniqueName}`, 'info');
        },
        onError: () => {
          addToast(`Failed to remove technique`, 'error');
        },
      }
    );
  };

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">ATT&CK Techniques</CardTitle>
            {canEdit(user) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowAddModal(true);
                  setSearchQuery('');
                }}
              >
                Add Technique
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <LoadingSpinner size="sm" />
          ) : mappedTechniques.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No ATT&CK techniques mapped
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {mappedTechniques.map((mapping) => (
                <Badge
                  key={mapping.id}
                  variant="secondary"
                  className="gap-1.5 pr-1 group"
                  title={`Added ${formatRelativeTime(mapping.created_at)}`}
                >
                  <span className="font-mono text-[10px] opacity-70">
                    {mapping.technique_external_id}
                  </span>
                  <span>{mapping.technique_name}</span>
                  {canEdit(user) && (
                    <button
                      onClick={() =>
                        handleUnmap(mapping.technique_id, mapping.technique_name)
                      }
                      disabled={unmapMutation.isPending}
                      className="ml-1 rounded-full hover:bg-foreground/10 h-4 w-4 inline-flex items-center justify-center text-xs opacity-60 group-hover:opacity-100 transition-opacity"
                      aria-label={`Remove technique ${mapping.technique_external_id}`}
                    >
                      x
                    </button>
                  )}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Technique Modal */}
      {showAddModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowAddModal(false);
          }}
        >
          <Card className="w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
            <CardHeader className="pb-3 shrink-0">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Add ATT&CK Technique</CardTitle>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="text-muted-foreground hover:text-foreground transition-colors p-1"
                  aria-label="Close modal"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
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
            <CardContent className="flex flex-col gap-3 overflow-hidden">
              <Input
                placeholder="Search by name or ID (e.g. T1059)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="shrink-0"
                autoFocus
              />
              <div className="overflow-y-auto min-h-0 max-h-[50vh] space-y-1 -mx-1 px-1">
                {techniquesLoading ? (
                  <div className="py-8">
                    <LoadingSpinner size="sm" />
                  </div>
                ) : filteredTechniques.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic py-4 text-center">
                    {searchQuery
                      ? 'No matching techniques found'
                      : 'All techniques already mapped'}
                  </p>
                ) : (
                  filteredTechniques.slice(0, 50).map((technique) => (
                    <button
                      key={technique.id}
                      onClick={() => handleMap(technique)}
                      disabled={mapMutation.isPending}
                      className="w-full flex items-center gap-3 rounded-md border border-border p-2.5 text-left hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50"
                    >
                      <Badge variant="outline" className="shrink-0 font-mono text-[10px]">
                        {technique.external_id}
                      </Badge>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">
                          {technique.name}
                        </p>
                        {technique.is_subtechnique && (
                          <p className="text-[10px] text-muted-foreground">
                            Sub-technique
                          </p>
                        )}
                      </div>
                    </button>
                  ))
                )}
                {filteredTechniques.length > 50 && (
                  <p className="text-xs text-muted-foreground text-center py-2">
                    Showing 50 of {filteredTechniques.length} results. Refine your search.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
