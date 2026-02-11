import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useCampaigns, useCreateCampaign } from '@/hooks/useCampaigns';
import { useThreatActors } from '@/hooks/useThreatActors';
import { useAuth } from '@/hooks/useAuth';
import { canEdit } from '@/lib/permissions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { formatDate, TLP_COLORS } from '@/lib/utils';
import type { CampaignFilters } from '@/types/campaign';

const CAMPAIGN_STATUSES = ['active', 'historical', 'suspected'];
const TLP_LEVELS = ['clear', 'green', 'amber', 'amber+strict', 'red'];

const STATUS_BADGE_VARIANT: Record<string, 'destructive' | 'secondary' | 'outline'> = {
  active: 'destructive',
  historical: 'secondary',
  suspected: 'outline',
};

export function CampaignsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<CampaignFilters>({ page: 1, size: 20 });
  const [nameSearch, setNameSearch] = useState('');
  const { data, isLoading } = useCampaigns(filters);
  const { data: actorsData } = useThreatActors({ size: 100 });
  const createMutation = useCreateCampaign();

  // Create dialog state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newStatus, setNewStatus] = useState('suspected');
  const [newThreatActorId, setNewThreatActorId] = useState('');
  const [newTlp, setNewTlp] = useState('clear');
  const [newObjective, setNewObjective] = useState('');

  const handleSearch = () => {
    setFilters((f) => ({ ...f, page: 1, name: nameSearch || undefined }));
  };

  const handleCreate = () => {
    if (!newName.trim()) return;
    createMutation.mutate(
      {
        name: newName.trim(),
        description: newDescription || undefined,
        status: newStatus,
        threat_actor_id: newThreatActorId || undefined,
        tlp: newTlp,
        objective: newObjective || undefined,
      },
      {
        onSuccess: () => {
          setShowCreate(false);
          setNewName('');
          setNewDescription('');
          setNewStatus('suspected');
          setNewThreatActorId('');
          setNewTlp('clear');
          setNewObjective('');
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Campaigns</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track malicious campaigns and their associated observables
          </p>
        </div>
        {canEdit(user) && (
          <Button onClick={() => setShowCreate(true)}>Create Campaign</Button>
        )}
      </div>

      {/* Search & Filters */}
      <div className="flex gap-2">
        <Input
          placeholder="Search by name..."
          value={nameSearch}
          onChange={(e) => setNameSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="max-w-sm"
        />
        <Select
          value={filters.status || ''}
          onChange={(e) =>
            setFilters((f) => ({
              ...f,
              page: 1,
              status: (e.target.value as CampaignFilters['status']) || undefined,
            }))
          }
          className="w-40"
        >
          <option value="">All Statuses</option>
          {CAMPAIGN_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </Select>
        <Button variant="outline" onClick={handleSearch}>
          Search
        </Button>
      </div>

      {/* Create Dialog */}
      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">New Campaign</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Name *
                </label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Campaign name"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Status
                </label>
                <Select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                  {CAMPAIGN_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Threat Actor
                </label>
                <Select
                  value={newThreatActorId}
                  onChange={(e) => setNewThreatActorId(e.target.value)}
                >
                  <option value="">None</option>
                  {actorsData?.items.map((actor) => (
                    <option key={actor.id} value={actor.id}>
                      {actor.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  TLP
                </label>
                <Select value={newTlp} onChange={(e) => setNewTlp(e.target.value)}>
                  {TLP_LEVELS.map((tlp) => (
                    <option key={tlp} value={tlp}>
                      TLP:{tlp.toUpperCase()}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground uppercase tracking-wider">
                Objective
              </label>
              <Input
                value={newObjective}
                onChange={(e) => setNewObjective(e.target.value)}
                placeholder="Campaign objective"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground uppercase tracking-wider">
                Description
              </label>
              <textarea
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[80px] resize-y"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Campaign description..."
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={!newName.trim() || createMutation.isPending}
              >
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <div className="space-y-3">
          {data?.items.length === 0 && (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No campaigns found. Create one to get started.
              </CardContent>
            </Card>
          )}
          {data?.items.map((campaign) => (
            <Link key={campaign.id} to={`/campaigns/${campaign.id}`} className="block">
              <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="font-semibold text-sm">{campaign.name}</span>
                      <Badge variant={STATUS_BADGE_VARIANT[campaign.status] || 'outline'}>
                        {campaign.status}
                      </Badge>
                      <Badge variant="outline" className={TLP_COLORS[campaign.tlp] || ''}>
                        TLP:{campaign.tlp.toUpperCase()}
                      </Badge>
                      {campaign.threat_actor && (
                        <Badge variant="secondary">{campaign.threat_actor.name}</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-6 shrink-0 text-xs text-muted-foreground">
                      <div>
                        <span className="uppercase tracking-wider block">First Seen</span>
                        <span className="text-foreground">
                          {campaign.first_seen ? formatDate(campaign.first_seen) : 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="uppercase tracking-wider block">Last Seen</span>
                        <span className="text-foreground">
                          {campaign.last_seen ? formatDate(campaign.last_seen) : 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="uppercase tracking-wider block">Observables</span>
                        <span className="text-foreground">{campaign.observables.length}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={filters.page === 1}
                onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) - 1 }))}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {filters.page || 1} of {data.pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={(filters.page || 1) >= data.pages}
                onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) + 1 }))}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
