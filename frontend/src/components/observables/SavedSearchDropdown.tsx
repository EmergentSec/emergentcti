import { useState, type FormEvent } from 'react';
import {
  useSavedSearches,
  useCreateSavedSearch,
  useDeleteSavedSearch,
  useSetDefaultSearch,
} from '@/hooks/useSavedSearches';
import { useAuth } from '@/hooks/useAuth';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
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
import { Badge } from '@/components/ui/badge';
import type { SavedSearchFilters } from '@/types/saved_search';

interface SavedSearchDropdownProps {
  currentFilters: SavedSearchFilters;
  onApply: (filters: SavedSearchFilters) => void;
}

export function SavedSearchDropdown({
  currentFilters,
  onApply,
}: SavedSearchDropdownProps) {
  const { user } = useAuth();
  const { data: savedSearches, isLoading } = useSavedSearches();
  const createMutation = useCreateSavedSearch();
  const deleteMutation = useDeleteSavedSearch();
  const setDefaultMutation = useSetDefaultSearch();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveShared, setSaveShared] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const defaultSearch = savedSearches?.find((s) => s.is_default);

  const hasActiveFilters =
    currentFilters.type ||
    currentFilters.value ||
    currentFilters.confidence_min ||
    currentFilters.tlp ||
    currentFilters.feed_id ||
    currentFilters.category ||
    currentFilters.tag;

  const handleApply = (filters: SavedSearchFilters) => {
    onApply(filters);
    setDropdownOpen(false);
  };

  const handleSaveSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!saveName.trim()) return;

    createMutation.mutate(
      {
        name: saveName.trim(),
        filters: currentFilters,
        is_shared: saveShared,
      },
      {
        onSuccess: () => {
          setSaveDialogOpen(false);
          setSaveName('');
          setSaveShared(false);
        },
      }
    );
  };

  const handleDelete = (id: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        setDeleteConfirmId(null);
      },
    });
  };

  const handleSetDefault = (id: string) => {
    setDefaultMutation.mutate(id);
  };

  const filterSummary = (filters: SavedSearchFilters): string => {
    const parts: string[] = [];
    if (filters.type) parts.push(filters.type);
    if (filters.value) parts.push(`"${filters.value}"`);
    if (filters.tlp) parts.push(`TLP:${filters.tlp.toUpperCase()}`);
    if (filters.confidence_min) parts.push(`${filters.confidence_min}+`);
    if (filters.feed_id) parts.push('feed');
    if (filters.category) parts.push(filters.category);
    if (filters.tag) parts.push(`#${filters.tag}`);
    return parts.length > 0 ? parts.join(', ') : 'No filters';
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger onClick={() => setDropdownOpen(!dropdownOpen)}>
          <Button variant="outline" size="sm" className="gap-2">
            <span className="text-base leading-none">{'\u2606'}</span>
            {defaultSearch ? defaultSearch.name : 'Saved Searches'}
            <span className="text-xs opacity-60">{'\u25BE'}</span>
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          open={dropdownOpen}
          onClose={() => setDropdownOpen(false)}
          align="start"
          className="w-72"
        >
          <DropdownMenuLabel>Saved Searches</DropdownMenuLabel>
          <DropdownMenuSeparator />

          {isLoading && (
            <div className="px-2 py-3 text-center text-sm text-muted-foreground">
              Loading...
            </div>
          )}

          {!isLoading && (!savedSearches || savedSearches.length === 0) && (
            <div className="px-2 py-3 text-center text-sm text-muted-foreground">
              No saved searches yet
            </div>
          )}

          {savedSearches && savedSearches.length > 0 && (
            <div className="max-h-64 overflow-y-auto">
              {savedSearches.map((search) => {
                const isOwner = user?.id === search.user_id;

                return (
                  <div
                    key={search.id}
                    className="group relative flex items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-accent"
                  >
                    {/* Default star */}
                    <button
                      className="shrink-0 text-sm leading-none transition-colors hover:text-yellow-400"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSetDefault(search.id);
                      }}
                      title={
                        search.is_default
                          ? 'Default search'
                          : 'Set as default'
                      }
                    >
                      {search.is_default ? '\u2605' : '\u2606'}
                    </button>

                    {/* Clickable search name and info */}
                    <button
                      className="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left"
                      onClick={() => handleApply(search.filters)}
                    >
                      <div className="flex w-full items-center gap-2">
                        <span className="truncate text-sm font-medium">
                          {search.name}
                        </span>
                        {search.is_shared && (
                          <Badge
                            variant="secondary"
                            className="shrink-0 text-[10px] px-1.5 py-0"
                          >
                            Shared
                          </Badge>
                        )}
                      </div>
                      <span className="truncate text-xs text-muted-foreground">
                        {filterSummary(search.filters)}
                      </span>
                    </button>

                    {/* Owner badge */}
                    {search.user && !isOwner && (
                      <span className="shrink-0 text-[10px] text-muted-foreground">
                        {search.user.username}
                      </span>
                    )}

                    {/* Delete button for owned searches */}
                    {isOwner && (
                      <button
                        className="shrink-0 rounded p-0.5 text-sm opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteConfirmId(search.id);
                        }}
                        title="Delete search"
                      >
                        {'\u2715'}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <DropdownMenuSeparator />

          {hasActiveFilters ? (
            <DropdownMenuItem
              onClick={() => {
                setDropdownOpen(false);
                setSaveDialogOpen(true);
              }}
            >
              <span className="mr-2">{'\u2795'}</span>
              Save Current Filters
            </DropdownMenuItem>
          ) : (
            <div className="px-2 py-1.5 text-xs text-muted-foreground">
              Set filters to save a search
            </div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Save Search Dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogClose onClose={() => setSaveDialogOpen(false)} />
          <DialogHeader>
            <DialogTitle>Save Search</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSaveSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="search-name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="search-name"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="e.g., High confidence IPs"
                maxLength={256}
                required
                autoFocus
              />
            </div>

            <div className="rounded-md border bg-muted/30 p-3">
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Filters to save
              </p>
              <p className="text-sm">{filterSummary(currentFilters)}</p>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={saveShared}
                onChange={(e) => setSaveShared(e.target.checked)}
                className="rounded border-input"
              />
              Share with all users
            </label>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setSaveDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Saving...' : 'Save Search'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteConfirmId(null);
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogClose onClose={() => setDeleteConfirmId(null)} />
          <DialogHeader>
            <DialogTitle>Delete Saved Search</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete this saved search? This action
            cannot be undone.
          </p>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeleteConfirmId(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteConfirmId) handleDelete(deleteConfirmId);
              }}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
