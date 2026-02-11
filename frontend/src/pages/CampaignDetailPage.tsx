import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  useCampaign,
  useUpdateCampaign,
  useDeleteCampaign,
  useUnlinkCampaignObservable,
  useLinkCampaignObservable,
  useCampaignTimeline,
} from '@/hooks/useCampaigns';
import { useThreatActors } from '@/hooks/useThreatActors';
import { useAuth } from '@/hooks/useAuth';
import { canEdit, canDelete } from '@/lib/permissions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { formatDate, TLP_COLORS } from '@/lib/utils';
import type { TLPLevel } from '@/types/observable';

const TLP_LEVELS: TLPLevel[] = ['clear', 'green', 'amber', 'amber+strict', 'red'];
const CAMPAIGN_STATUSES = ['active', 'historical', 'suspected'];

const STATUS_BADGE_VARIANT: Record<string, 'destructive' | 'secondary' | 'outline'> = {
  active: 'destructive',
  historical: 'secondary',
  suspected: 'outline',
};

const TIMELINE_EVENT_COLORS: Record<string, string> = {
  campaign_created: 'bg-blue-500',
  campaign_first_seen: 'bg-green-500',
  campaign_last_seen: 'bg-red-500',
  observable_linked: 'bg-purple-500',
  observable_first_seen: 'bg-amber-500',
};

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: campaign, isLoading, error } = useCampaign(id || '');
  const { data: timeline } = useCampaignTimeline(id || '');
  const { data: actorsData } = useThreatActors({ size: 100 });
  const updateMutation = useUpdateCampaign();
  const deleteMutation = useDeleteCampaign();
  const unlinkObsMutation = useUnlinkCampaignObservable();
  const linkObsMutation = useLinkCampaignObservable();

  // Edit state
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [editThreatActorId, setEditThreatActorId] = useState('');
  const [editTlp, setEditTlp] = useState<TLPLevel>('clear');
  const [editObjective, setEditObjective] = useState('');

  // Link observable state
  const [showLinkObs, setShowLinkObs] = useState(false);
  const [linkObsId, setLinkObsId] = useState('');

  const startEditing = () => {
    if (!campaign) return;
    setEditName(campaign.name);
    setEditDescription(campaign.description || '');
    setEditStatus(campaign.status);
    setEditThreatActorId(campaign.threat_actor_id || '');
    setEditTlp(campaign.tlp as TLPLevel);
    setEditObjective(campaign.objective || '');
    setEditing(true);
  };

  const handleSave = () => {
    if (!id) return;
    updateMutation.mutate(
      {
        id,
        data: {
          name: editName,
          description: editDescription || undefined,
          status: editStatus,
          threat_actor_id: editThreatActorId || null,
          tlp: editTlp,
          objective: editObjective || undefined,
        },
      },
      { onSuccess: () => setEditing(false) }
    );
  };

  const handleDelete = () => {
    if (!id) return;
    if (window.confirm('Are you sure you want to delete this campaign?')) {
      deleteMutation.mutate(id, {
        onSuccess: () => navigate('/campaigns'),
      });
    }
  };

  const handleLinkObservable = () => {
    if (!id || !linkObsId.trim()) return;
    linkObsMutation.mutate(
      { campaignId: id, observableId: linkObsId.trim() },
      {
        onSuccess: () => {
          setLinkObsId('');
          setShowLinkObs(false);
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg text-muted-foreground">Campaign not found</p>
        <Button variant="outline" onClick={() => navigate('/campaigns')}>
          Back to Campaigns
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/campaigns" className="hover:text-foreground transition-colors">
          Campaigns
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium">{campaign.name}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{campaign.name}</h1>
            <Badge variant={STATUS_BADGE_VARIANT[campaign.status] || 'outline'}>
              {campaign.status}
            </Badge>
            <Badge variant="outline" className={TLP_COLORS[campaign.tlp] || ''}>
              TLP:{campaign.tlp.toUpperCase()}
            </Badge>
          </div>
          {campaign.threat_actor && (
            <div className="mt-2">
              <span className="text-sm text-muted-foreground">Attributed to: </span>
              <Link
                to={`/threat-actors/${campaign.threat_actor.id}`}
                className="text-sm font-medium text-primary hover:underline"
              >
                {campaign.threat_actor.name}
              </Link>
            </div>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          {!editing ? (
            <>
              {canEdit(user) && (
                <Button variant="outline" size="sm" onClick={startEditing}>
                  Edit
                </Button>
              )}
              {canDelete(user) && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </Button>
              )}
            </>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={updateMutation.isPending}
              >
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* LEFT COLUMN */}
        <div className="lg:col-span-3 space-y-6">
          {/* Description */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Description</CardTitle>
            </CardHeader>
            <CardContent>
              {editing ? (
                <textarea
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[100px] resize-y"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Add a description..."
                />
              ) : (
                <p
                  className={
                    campaign.description
                      ? 'text-sm'
                      : 'text-sm text-muted-foreground italic'
                  }
                >
                  {campaign.description || 'No description'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Objective */}
          {(campaign.objective || editing) && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Objective</CardTitle>
              </CardHeader>
              <CardContent>
                {editing ? (
                  <textarea
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[80px] resize-y"
                    value={editObjective}
                    onChange={(e) => setEditObjective(e.target.value)}
                    placeholder="Campaign objective..."
                  />
                ) : (
                  <p className="text-sm">{campaign.objective}</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Linked Observables */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  Linked Observables ({campaign.observables.length})
                </CardTitle>
                {canEdit(user) && !showLinkObs && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowLinkObs(true)}
                    className="h-7 px-2 text-muted-foreground hover:text-foreground"
                  >
                    + Link
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {showLinkObs && (
                <div className="flex items-center gap-2 mb-4">
                  <Input
                    value={linkObsId}
                    onChange={(e) => setLinkObsId(e.target.value)}
                    placeholder="Observable UUID"
                    className="h-8 text-sm"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleLinkObservable}
                    disabled={!linkObsId.trim() || linkObsMutation.isPending}
                    className="h-8"
                  >
                    Link
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowLinkObs(false);
                      setLinkObsId('');
                    }}
                    className="h-8"
                  >
                    Cancel
                  </Button>
                </div>
              )}
              {campaign.observables.length > 0 ? (
                <div className="space-y-2">
                  {campaign.observables.map((obs) => (
                    <div
                      key={obs.id}
                      className="flex items-center justify-between rounded-md border border-border p-2.5"
                    >
                      <Link
                        to={`/observables/${obs.id}`}
                        className="flex items-center gap-2 hover:text-primary transition-colors min-w-0"
                      >
                        <Badge variant="secondary" className="shrink-0 text-xs">
                          {obs.type}
                        </Badge>
                        <span className="text-sm font-mono truncate">{obs.value}</span>
                      </Link>
                      {canEdit(user) && (
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            unlinkObsMutation.mutate({
                              campaignId: id!,
                              observableId: obs.id,
                            });
                          }}
                          className="text-muted-foreground hover:text-destructive transition-colors p-1 ml-2 shrink-0"
                          aria-label="Unlink observable"
                        >
                          x
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No linked observables</p>
              )}
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {timeline && timeline.events.length > 0 ? (
                <div className="relative">
                  <div className="absolute left-3 top-0 bottom-0 w-px bg-border" />
                  <div className="space-y-4">
                    {timeline.events.map((event, idx) => (
                      <div key={idx} className="relative flex items-start gap-4 pl-8">
                        <div
                          className={`absolute left-1.5 top-1.5 h-3 w-3 rounded-full ${
                            TIMELINE_EVENT_COLORS[event.event_type] || 'bg-gray-500'
                          }`}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm">{event.description}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-muted-foreground">
                              {formatDate(event.timestamp)}
                            </span>
                            {event.observable_id && (
                              <Link
                                to={`/observables/${event.observable_id}`}
                                className="text-xs text-primary hover:underline"
                              >
                                View Observable
                              </Link>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No timeline events</p>
              )}
            </CardContent>
          </Card>

          {/* External References */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">External References</CardTitle>
            </CardHeader>
            <CardContent>
              {campaign.external_references &&
              campaign.external_references.length > 0 ? (
                <div className="space-y-3">
                  {campaign.external_references.map((ref, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-3 rounded-md border border-border p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">{ref.source}</p>
                        {ref.description && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {ref.description}
                          </p>
                        )}
                        <a
                          href={ref.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-400 hover:text-blue-300 hover:underline mt-1 inline-block break-all"
                        >
                          {ref.url}
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No external references</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* RIGHT COLUMN */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Metadata</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {editing ? (
                <>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Name</p>
                    <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Status</p>
                    <Select value={editStatus} onChange={(e) => setEditStatus(e.target.value)}>
                      {CAMPAIGN_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s.charAt(0).toUpperCase() + s.slice(1)}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Threat Actor
                    </p>
                    <Select
                      value={editThreatActorId}
                      onChange={(e) => setEditThreatActorId(e.target.value)}
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
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">TLP</p>
                    <Select
                      value={editTlp}
                      onChange={(e) => setEditTlp(e.target.value as TLPLevel)}
                    >
                      {TLP_LEVELS.map((tlp) => (
                        <option key={tlp} value={tlp}>
                          TLP:{tlp.toUpperCase()}
                        </option>
                      ))}
                    </Select>
                  </div>
                </>
              ) : (
                <>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Status</p>
                    <Badge variant={STATUS_BADGE_VARIANT[campaign.status] || 'outline'}>
                      {campaign.status}
                    </Badge>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Threat Actor
                    </p>
                    {campaign.threat_actor ? (
                      <Link
                        to={`/threat-actors/${campaign.threat_actor.id}`}
                        className="text-sm font-medium text-primary hover:underline"
                      >
                        {campaign.threat_actor.name}
                      </Link>
                    ) : (
                      <span className="text-sm text-muted-foreground">Unattributed</span>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">TLP</p>
                    <Badge variant="outline" className={TLP_COLORS[campaign.tlp] || ''}>
                      TLP:{campaign.tlp.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      First Seen
                    </p>
                    <p className="text-sm">
                      {campaign.first_seen ? formatDate(campaign.first_seen) : 'N/A'}
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Last Seen
                    </p>
                    <p className="text-sm">
                      {campaign.last_seen ? formatDate(campaign.last_seen) : 'N/A'}
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Created</p>
                    <p className="text-sm">{formatDate(campaign.created_at)}</p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Updated</p>
                    <p className="text-sm">{formatDate(campaign.updated_at)}</p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
