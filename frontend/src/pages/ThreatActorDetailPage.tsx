import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  useThreatActor,
  useUpdateThreatActor,
  useDeleteThreatActor,
  useUnlinkThreatActorObservable,
  useUnlinkThreatActorTechnique,
  useThreatActorCampaigns,
  useLinkThreatActorObservable,
} from '@/hooks/useThreatActors';
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

export function ThreatActorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: actor, isLoading, error } = useThreatActor(id || '');
  const { data: campaigns = [] } = useThreatActorCampaigns(id || '');
  const updateMutation = useUpdateThreatActor();
  const deleteMutation = useDeleteThreatActor();
  const unlinkObservableMutation = useUnlinkThreatActorObservable();
  const unlinkTechniqueMutation = useUnlinkThreatActorTechnique();
  const linkObservableMutation = useLinkThreatActorObservable();

  // Edit state
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editAliases, setEditAliases] = useState('');
  const [editCountry, setEditCountry] = useState('');
  const [editMotivation, setEditMotivation] = useState('');
  const [editSophistication, setEditSophistication] = useState('');
  const [editTlp, setEditTlp] = useState<TLPLevel>('clear');
  const [editDescription, setEditDescription] = useState('');

  // Link observable state
  const [showLinkObs, setShowLinkObs] = useState(false);
  const [linkObsId, setLinkObsId] = useState('');

  const startEditing = () => {
    if (!actor) return;
    setEditName(actor.name);
    setEditAliases(actor.aliases?.join(', ') || '');
    setEditCountry(actor.country || '');
    setEditMotivation(actor.motivation || '');
    setEditSophistication(actor.sophistication || '');
    setEditTlp(actor.tlp as TLPLevel);
    setEditDescription(actor.description || '');
    setEditing(true);
  };

  const handleSave = () => {
    if (!id) return;
    updateMutation.mutate(
      {
        id,
        data: {
          name: editName,
          aliases: editAliases ? editAliases.split(',').map((a) => a.trim()).filter(Boolean) : [],
          country: editCountry || undefined,
          motivation: editMotivation || undefined,
          sophistication: editSophistication || undefined,
          tlp: editTlp,
          description: editDescription || undefined,
        },
      },
      { onSuccess: () => setEditing(false) }
    );
  };

  const handleDelete = () => {
    if (!id) return;
    if (window.confirm('Are you sure you want to delete this threat actor?')) {
      deleteMutation.mutate(id, {
        onSuccess: () => navigate('/threat-actors'),
      });
    }
  };

  const handleLinkObservable = () => {
    if (!id || !linkObsId.trim()) return;
    linkObservableMutation.mutate(
      { actorId: id, observableId: linkObsId.trim() },
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

  if (error || !actor) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg text-muted-foreground">Threat actor not found</p>
        <Button variant="outline" onClick={() => navigate('/threat-actors')}>
          Back to Threat Actors
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/threat-actors" className="hover:text-foreground transition-colors">
          Threat Actors
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium">{actor.name}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{actor.name}</h1>
            {actor.country && (
              <Badge variant="outline" className="text-sm">
                {actor.country}
              </Badge>
            )}
            <Badge variant="outline" className={TLP_COLORS[actor.tlp] || ''}>
              TLP:{actor.tlp.toUpperCase()}
            </Badge>
          </div>
          {actor.aliases && actor.aliases.length > 0 && (
            <div className="flex items-center gap-2 mt-2">
              <span className="text-sm text-muted-foreground">Also known as:</span>
              {actor.aliases.map((alias) => (
                <Badge key={alias} variant="secondary">
                  {alias}
                </Badge>
              ))}
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
                <p className={actor.description ? 'text-sm' : 'text-sm text-muted-foreground italic'}>
                  {actor.description || 'No description'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Linked Observables */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  Linked Observables ({actor.observables.length})
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
                    disabled={!linkObsId.trim() || linkObservableMutation.isPending}
                    className="h-8"
                  >
                    Link
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setShowLinkObs(false); setLinkObsId(''); }}
                    className="h-8"
                  >
                    Cancel
                  </Button>
                </div>
              )}
              {actor.observables.length > 0 ? (
                <div className="space-y-2">
                  {actor.observables.map((obs) => (
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
                            unlinkObservableMutation.mutate({
                              actorId: id!,
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

          {/* Linked Techniques */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                ATT&CK Techniques ({actor.techniques.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {actor.techniques.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {actor.techniques.map((tech) => (
                    <div
                      key={tech.id}
                      className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5"
                    >
                      <Badge variant="outline" className="text-xs">
                        {tech.external_id}
                      </Badge>
                      <span className="text-sm">{tech.name}</span>
                      {canEdit(user) && (
                        <button
                          onClick={() =>
                            unlinkTechniqueMutation.mutate({
                              actorId: id!,
                              techniqueId: tech.id,
                            })
                          }
                          className="text-muted-foreground hover:text-destructive transition-colors p-0.5 ml-1"
                          aria-label="Unlink technique"
                        >
                          x
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No linked techniques</p>
              )}
            </CardContent>
          </Card>

          {/* Campaigns */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Campaigns ({campaigns.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {campaigns.length > 0 ? (
                <div className="space-y-2">
                  {campaigns.map((campaign) => (
                    <Link
                      key={campaign.id}
                      to={`/campaigns/${campaign.id}`}
                      className="flex items-center justify-between rounded-md border border-border p-2.5 hover:bg-accent/50 transition-colors"
                    >
                      <span className="text-sm font-medium">{campaign.name}</span>
                      <div className="flex items-center gap-3">
                        <Badge
                          variant={
                            campaign.status === 'active'
                              ? 'destructive'
                              : campaign.status === 'historical'
                              ? 'secondary'
                              : 'outline'
                          }
                        >
                          {campaign.status}
                        </Badge>
                        {campaign.first_seen && (
                          <span className="text-xs text-muted-foreground">
                            {formatDate(campaign.first_seen)}
                          </span>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No linked campaigns</p>
              )}
            </CardContent>
          </Card>

          {/* External References */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">External References</CardTitle>
            </CardHeader>
            <CardContent>
              {actor.external_references && actor.external_references.length > 0 ? (
                <div className="space-y-3">
                  {actor.external_references.map((ref, idx) => (
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
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Aliases</p>
                    <Input
                      value={editAliases}
                      onChange={(e) => setEditAliases(e.target.value)}
                      placeholder="Comma-separated"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Country</p>
                    <Input value={editCountry} onChange={(e) => setEditCountry(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Motivation</p>
                    <Select value={editMotivation} onChange={(e) => setEditMotivation(e.target.value)}>
                      <option value="">None</option>
                      <option value="espionage">Espionage</option>
                      <option value="financial">Financial</option>
                      <option value="hacktivism">Hacktivism</option>
                      <option value="destruction">Destruction</option>
                      <option value="unknown">Unknown</option>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Sophistication</p>
                    <Select value={editSophistication} onChange={(e) => setEditSophistication(e.target.value)}>
                      <option value="">None</option>
                      <option value="none">None</option>
                      <option value="minimal">Minimal</option>
                      <option value="intermediate">Intermediate</option>
                      <option value="advanced">Advanced</option>
                      <option value="expert">Expert</option>
                      <option value="innovator">Innovator</option>
                      <option value="strategic">Strategic</option>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">TLP</p>
                    <Select value={editTlp} onChange={(e) => setEditTlp(e.target.value as TLPLevel)}>
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
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Country</p>
                    <p className="text-sm">{actor.country || 'Unknown'}</p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Motivation</p>
                    <p className="text-sm capitalize">{actor.motivation || 'Unknown'}</p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Sophistication</p>
                    <p className="text-sm capitalize">{actor.sophistication || 'Unknown'}</p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">TLP</p>
                    <Badge variant="outline" className={TLP_COLORS[actor.tlp] || ''}>
                      TLP:{actor.tlp.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">First Seen</p>
                    <p className="text-sm">
                      {actor.first_seen ? formatDate(actor.first_seen) : 'N/A'}
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Last Seen</p>
                    <p className="text-sm">
                      {actor.last_seen ? formatDate(actor.last_seen) : 'N/A'}
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Created</p>
                    <p className="text-sm">{formatDate(actor.created_at)}</p>
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Updated</p>
                    <p className="text-sm">{formatDate(actor.updated_at)}</p>
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
