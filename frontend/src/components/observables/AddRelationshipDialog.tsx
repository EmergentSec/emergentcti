import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { ObservableBadge } from '@/components/observables/ObservableBadge';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useCreateRelationship } from '@/hooks/useRelationships';
import { useToast } from '@/contexts/ToastContext';
import { searchObservables } from '@/api/search';
import { RELATIONSHIP_TYPES } from '@/types/relationship';
import type { RelationshipType } from '@/types/relationship';
import type { SearchHit } from '@/types/search';

interface AddRelationshipDialogProps {
  observableId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddRelationshipDialog({
  observableId,
  open,
  onOpenChange,
}: AddRelationshipDialogProps) {
  const { addToast } = useToast();
  const createMutation = useCreateRelationship();

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchHit[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedTarget, setSelectedTarget] = useState<SearchHit | null>(null);
  const [relationshipType, setRelationshipType] = useState<RelationshipType>('related-to');
  const [confidence, setConfidence] = useState(50);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetForm = useCallback(() => {
    setSearchQuery('');
    setSearchResults([]);
    setSelectedTarget(null);
    setRelationshipType('related-to');
    setConfidence(50);
    setIsSearching(false);
  }, []);

  useEffect(() => {
    if (!open) {
      resetForm();
    }
  }, [open, resetForm]);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (searchQuery.trim().length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const response = await searchObservables({ q: searchQuery.trim(), size: 10 });
        // Filter out the current observable from results
        const filtered = response.hits.filter((hit) => hit.id !== observableId);
        setSearchResults(filtered);
      } catch {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [searchQuery, observableId]);

  const handleSubmit = () => {
    if (!selectedTarget) return;

    createMutation.mutate(
      {
        observableId,
        data: {
          target_id: selectedTarget.id,
          relationship_type: relationshipType,
          confidence,
        },
      },
      {
        onSuccess: () => {
          addToast('Relationship created successfully', 'success');
          onOpenChange(false);
        },
        onError: () => {
          addToast('Failed to create relationship', 'error');
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogClose onClose={() => onOpenChange(false)} />
        <DialogHeader>
          <DialogTitle>Add Relationship</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Target Observable Search */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Target Observable</label>
            {selectedTarget ? (
              <div className="flex items-center gap-2 rounded-md border border-input bg-muted/50 p-2">
                <ObservableBadge type={selectedTarget.type} />
                <span className="text-sm font-mono truncate flex-1">
                  {selectedTarget.value}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedTarget(null);
                    setSearchQuery('');
                  }}
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                >
                  x
                </Button>
              </div>
            ) : (
              <>
                <Input
                  placeholder="Search observables..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                />
                {/* Search Results */}
                {(isSearching || searchResults.length > 0) && (
                  <div className="max-h-48 overflow-y-auto rounded-md border border-input bg-background">
                    {isSearching ? (
                      <div className="flex items-center justify-center py-4">
                        <LoadingSpinner size="sm" />
                      </div>
                    ) : searchResults.length > 0 ? (
                      searchResults.map((hit) => (
                        <button
                          key={hit.id}
                          type="button"
                          className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-muted/50 transition-colors border-b border-border last:border-0"
                          onClick={() => {
                            setSelectedTarget(hit);
                            setSearchResults([]);
                            setSearchQuery('');
                          }}
                        >
                          <ObservableBadge type={hit.type} />
                          <span className="text-sm font-mono truncate">
                            {hit.value}
                          </span>
                        </button>
                      ))
                    ) : null}
                  </div>
                )}
                {searchQuery.trim().length >= 2 &&
                  !isSearching &&
                  searchResults.length === 0 && (
                    <p className="text-xs text-muted-foreground px-1">
                      No observables found
                    </p>
                  )}
              </>
            )}
          </div>

          {/* Relationship Type */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Relationship Type</label>
            <Select
              value={relationshipType}
              onChange={(e) =>
                setRelationshipType(e.target.value as RelationshipType)
              }
            >
              {RELATIONSHIP_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Select>
          </div>

          {/* Confidence */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              Confidence
              <Badge variant="secondary" className="ml-2 tabular-nums">
                {confidence}
              </Badge>
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={confidence}
                onChange={(e) => setConfidence(parseInt(e.target.value, 10))}
                className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <Input
                type="number"
                min="0"
                max="100"
                value={confidence}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val) && val >= 0 && val <= 100) {
                    setConfidence(val);
                  }
                }}
                className="w-16 h-8 text-sm text-center"
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!selectedTarget || createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating...' : 'Create Relationship'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
