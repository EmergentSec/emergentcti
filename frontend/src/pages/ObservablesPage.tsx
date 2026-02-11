import { useState, useCallback, useEffect, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useObservables, useCreateObservable, useBulkUpdateObservables, useBulkDeleteObservables } from '@/hooks/useObservables';
import { useFeeds } from '@/hooks/useFeeds';
import { useAuth } from '@/hooks/useAuth';
import { canEdit, canDelete } from '@/lib/permissions';
import { ObservableTable } from '@/components/observables/ObservableTable';
import { ExportMenu } from '@/components/observables/ExportMenu';
import { SavedSearchDropdown } from '@/components/observables/SavedSearchDropdown';
import { Pagination } from '@/components/common/Pagination';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import { useToast } from '@/contexts/ToastContext';
import { bulkEnrich } from '@/api/observables';
import { exportSelected } from '@/api/export';
import type { ObservableType, TLPLevel, ObservableFilters } from '@/types/observable';
import { OBSERVABLE_CATEGORIES } from '@/types/observable';
import type { SavedSearchFilters } from '@/types/saved_search';

const OBSERVABLE_TYPES: ObservableType[] = [
  'ip-addr',
  'domain-name',
  'url',
  'file-hash',
  'email-addr',
  'command-line',
  'user-agent',
  'certificate',
  'asn',
  'cidr',
];

const TLP_LEVELS: TLPLevel[] = ['clear', 'green', 'amber', 'amber+strict', 'red'];

export function ObservablesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  // Parse filters from URL
  const filters: ObservableFilters = {
    page: parseInt(searchParams.get('page') || '1', 10),
    size: 20,
    type: (searchParams.get('type') as ObservableType) || '',
    value: searchParams.get('value') || '',
    confidence_min: searchParams.get('confidence_min')
      ? parseInt(searchParams.get('confidence_min')!, 10)
      : undefined,
    tlp: (searchParams.get('tlp') as TLPLevel) || '',
    feed_id: searchParams.get('feed_id') || undefined,
    is_active: searchParams.get('is_active') || '',
  };

  const { data, isLoading } = useObservables(filters);
  const createMutation = useCreateObservable();
  const { data: feeds } = useFeeds();
  const bulkUpdateMutation = useBulkUpdateObservables();
  const bulkDeleteMutation = useBulkDeleteObservables();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const { addToast } = useToast();

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (!data?.items) return;
    setSelectedIds((prev) => {
      const allSelected = data.items.every((obs) => prev.has(obs.id));
      if (allSelected) return new Set();
      return new Set(data.items.map((obs) => obs.id));
    });
  };

  // Clear selection on data change
  useEffect(() => {
    setSelectedIds(new Set());
  }, [data]);

  // Update URL params when filters change
  const updateFilter = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams);
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      // Reset to page 1 on filter change
      if (key !== 'page') {
        params.delete('page');
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const handlePageChange = useCallback(
    (page: number) => {
      updateFilter('page', page.toString());
    },
    [updateFilter]
  );

  // Apply saved search filters to URL params
  const handleApplySavedSearch = useCallback(
    (savedFilters: SavedSearchFilters) => {
      const params = new URLSearchParams();
      if (savedFilters.type) params.set('type', savedFilters.type);
      if (savedFilters.value) params.set('value', savedFilters.value);
      if (savedFilters.confidence_min != null)
        params.set('confidence_min', String(savedFilters.confidence_min));
      if (savedFilters.tlp) params.set('tlp', savedFilters.tlp);
      if (savedFilters.feed_id) params.set('feed_id', savedFilters.feed_id);
      // category and tag are part of saved search but not currently URL params;
      // set them if present so they can be extended later
      setSearchParams(params, { replace: true });
    },
    [setSearchParams]
  );

  // Build current filter state for SavedSearchDropdown
  const currentSavedSearchFilters: SavedSearchFilters = {
    type: filters.type || null,
    value: filters.value || null,
    confidence_min: filters.confidence_min ?? null,
    tlp: filters.tlp || null,
    feed_id: filters.feed_id || null,
  };

  // Add observable form state
  const [newType, setNewType] = useState<ObservableType>('ip-addr');
  const [newValue, setNewValue] = useState('');
  const [newTlp, setNewTlp] = useState<TLPLevel>('clear');
  const [newConfidence, setNewConfidence] = useState('50');
  const [newTags, setNewTags] = useState('');
  const [newCategory, setNewCategory] = useState('');

  const handleAddSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate(
      {
        type: newType,
        value: newValue,
        tlp: newTlp,
        confidence_score: parseInt(newConfidence, 10),
        tags: newTags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        category: newCategory || undefined,
      },
      {
        onSuccess: () => {
          setAddDialogOpen(false);
          setNewValue('');
          setNewTags('');
          setNewCategory('');
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Observables</h1>
          <p className="text-muted-foreground">
            {data?.total !== undefined
              ? `${data.total.toLocaleString()} indicators tracked`
              : 'Loading...'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ExportMenu
            filters={{
              type: filters.type || undefined,
              value: filters.value || undefined,
              confidence_min: filters.confidence_min,
              tlp: filters.tlp || undefined,
              feed_id: filters.feed_id,
            }}
          />
          {canEdit(user) && (
            <Button onClick={() => setAddDialogOpen(true)}>
              + Add Observable
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <SavedSearchDropdown
          currentFilters={currentSavedSearchFilters}
          onApply={handleApplySavedSearch}
        />
        <Input
          placeholder="Search by value..."
          value={filters.value || ''}
          onChange={(e) => updateFilter('value', e.target.value)}
          className="w-64"
        />
        <Select
          value={filters.type || ''}
          onChange={(e) => updateFilter('type', e.target.value)}
          className="w-40"
        >
          <option value="">All Types</option>
          {OBSERVABLE_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </Select>
        <Select
          value={filters.tlp || ''}
          onChange={(e) => updateFilter('tlp', e.target.value)}
          className="w-40"
        >
          <option value="">All TLP</option>
          {TLP_LEVELS.map((tlp) => (
            <option key={tlp} value={tlp}>
              TLP:{tlp.toUpperCase()}
            </option>
          ))}
        </Select>
        <Select
          value={filters.confidence_min?.toString() || ''}
          onChange={(e) => updateFilter('confidence_min', e.target.value)}
          className="w-48"
        >
          <option value="">Any Confidence</option>
          <option value="80">High (80+)</option>
          <option value="60">Medium (60+)</option>
          <option value="40">Low (40+)</option>
          <option value="20">Very Low (20+)</option>
        </Select>
        <Select
          value={filters.feed_id || ''}
          onChange={(e) => updateFilter('feed_id', e.target.value)}
          className="w-48"
        >
          <option value="">All Sources</option>
          {feeds?.map((feed) => (
            <option key={feed.id} value={feed.id}>
              {feed.name}
            </option>
          ))}
        </Select>
        <Select
          value={filters.is_active || ''}
          onChange={(e) => updateFilter('is_active', e.target.value)}
          className="w-40"
        >
          <option value="">All Status</option>
          <option value="true">Active Only</option>
          <option value="false">Expired Only</option>
        </Select>
      </div>

      {/* Bulk Actions Toolbar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-3">
          <span className="text-sm font-medium">
            {selectedIds.size} selected
          </span>
          <div className="h-4 w-px bg-border" />
          {canEdit(user) && (
            <>
              <Select
                className="w-36 h-8 text-xs"
                value=""
                onChange={(e) => {
                  if (e.target.value) {
                    bulkUpdateMutation.mutate(
                      { ids: Array.from(selectedIds), updates: { tlp: e.target.value } },
                      { onSuccess: () => setSelectedIds(new Set()) }
                    );
                  }
                }}
              >
                <option value="">Change TLP...</option>
                {TLP_LEVELS.map((tlp) => (
                  <option key={tlp} value={tlp}>TLP:{tlp.toUpperCase()}</option>
                ))}
              </Select>
              <Select
                className="w-44 h-8 text-xs"
                value=""
                onChange={(e) => {
                  if (e.target.value) {
                    bulkUpdateMutation.mutate(
                      { ids: Array.from(selectedIds), updates: { category: e.target.value } },
                      { onSuccess: () => setSelectedIds(new Set()) }
                    );
                  }
                }}
              >
                <option value="">Change Category...</option>
                {OBSERVABLE_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </option>
                ))}
              </Select>
            </>
          )}
          {canEdit(user) && (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                try {
                  const result = await bulkEnrich(Array.from(selectedIds));
                  addToast(`Enrichment dispatched for ${result.dispatched} provider(s)`, 'success');
                } catch {
                  addToast('Failed to dispatch enrichment', 'error');
                }
              }}
            >
              Enrich Selected
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger onClick={() => setExportDropdownOpen(!exportDropdownOpen)}>
              <Button size="sm" variant="outline">
                Export Selected
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent open={exportDropdownOpen} onClose={() => setExportDropdownOpen(false)}>
              <DropdownMenuItem
                onClick={async () => {
                  setExportDropdownOpen(false);
                  try {
                    await exportSelected(Array.from(selectedIds), 'stix');
                    addToast('STIX export downloaded', 'success');
                  } catch {
                    addToast('Export failed', 'error');
                  }
                }}
              >
                STIX 2.1
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={async () => {
                  setExportDropdownOpen(false);
                  try {
                    await exportSelected(Array.from(selectedIds), 'csv');
                    addToast('CSV export downloaded', 'success');
                  } catch {
                    addToast('Export failed', 'error');
                  }
                }}
              >
                CSV
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={async () => {
                  setExportDropdownOpen(false);
                  try {
                    await exportSelected(Array.from(selectedIds), 'json');
                    addToast('JSON export downloaded', 'success');
                  } catch {
                    addToast('Export failed', 'error');
                  }
                }}
              >
                JSON
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {canDelete(user) && (
            <Button
              size="sm"
              variant="destructive"
              onClick={() => {
                if (window.confirm(`Delete ${selectedIds.size} observables?`)) {
                  bulkDeleteMutation.mutate(Array.from(selectedIds), {
                    onSuccess: () => setSelectedIds(new Set()),
                  });
                }
              }}
              disabled={bulkDeleteMutation.isPending}
            >
              {bulkDeleteMutation.isPending ? 'Deleting...' : `Delete (${selectedIds.size})`}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setSelectedIds(new Set())}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Table */}
      <ObservableTable
        observables={data?.items || []}
        isLoading={isLoading}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelect}
        onToggleSelectAll={toggleSelectAll}
      />

      {/* Pagination */}
      {data && data.pages > 1 && (
        <Pagination
          page={data.page}
          totalPages={data.pages}
          onPageChange={handlePageChange}
        />
      )}

      {/* Add Observable Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogClose onClose={() => setAddDialogOpen(false)} />
          <DialogHeader>
            <DialogTitle>Add Observable</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="obs-type" className="text-sm font-medium">
                Type
              </label>
              <Select
                id="obs-type"
                value={newType}
                onChange={(e) =>
                  setNewType(e.target.value as ObservableType)
                }
              >
                {OBSERVABLE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <label htmlFor="obs-value" className="text-sm font-medium">
                Value
              </label>
              <Input
                id="obs-value"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder="e.g., 192.168.1.1"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label htmlFor="obs-tlp" className="text-sm font-medium">
                  TLP
                </label>
                <Select
                  id="obs-tlp"
                  value={newTlp}
                  onChange={(e) =>
                    setNewTlp(e.target.value as TLPLevel)
                  }
                >
                  {TLP_LEVELS.map((tlp) => (
                    <option key={tlp} value={tlp}>
                      TLP:{tlp.toUpperCase()}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="obs-confidence"
                  className="text-sm font-medium"
                >
                  Confidence
                </label>
                <Input
                  id="obs-confidence"
                  type="number"
                  min="0"
                  max="100"
                  value={newConfidence}
                  onChange={(e) => setNewConfidence(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="obs-tags" className="text-sm font-medium">
                Tags (comma-separated)
              </label>
              <Input
                id="obs-tags"
                value={newTags}
                onChange={(e) => setNewTags(e.target.value)}
                placeholder="malware, botnet, c2"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="obs-category" className="text-sm font-medium">
                Category
              </label>
              <Select
                id="obs-category"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
              >
                <option value="">No Category</option>
                {OBSERVABLE_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </option>
                ))}
              </Select>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setAddDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Adding...' : 'Add Observable'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
