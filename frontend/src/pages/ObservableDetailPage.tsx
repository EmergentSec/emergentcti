import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  useObservable,
  useUpdateObservable,
  useDeleteObservable,
  useObservableNotes,
  useCreateNote,
  useDeleteNote,
} from '@/hooks/useObservables';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/contexts/ToastContext';
import { canEdit, canDelete, isAnalyst } from '@/lib/permissions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { ObservableBadge } from '@/components/observables/ObservableBadge';
import { RelationshipPanel } from '@/components/observables/RelationshipPanel';
import { RelationshipGraph } from '@/components/observables/RelationshipGraph';
import { EnrichmentPanel } from '@/components/observables/EnrichmentPanel';
import { AttackTechniquesPanel } from '@/components/observables/AttackTechniquesPanel';
import { ConfidenceMeter } from '@/components/common/ConfidenceMeter';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useThreatActorsForObservable } from '@/hooks/useThreatActors';
import { useCampaignsForObservable } from '@/hooks/useCampaigns';
import { formatDate, formatRelativeTime, TLP_COLORS } from '@/lib/utils';
import type { TLPLevel } from '@/types/observable';
import { OBSERVABLE_CATEGORIES } from '@/types/observable';

const TLP_LEVELS: TLPLevel[] = ['clear', 'green', 'amber', 'amber+strict', 'red'];

export function ObservableDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToast } = useToast();
  const { data: observable, isLoading, error } = useObservable(id || '');
  const updateMutation = useUpdateObservable();
  const deleteMutation = useDeleteObservable();

  // Notes
  const { data: notes = [] } = useObservableNotes(id || '');
  const createNoteMutation = useCreateNote();
  const deleteNoteMutation = useDeleteNote();
  const [noteContent, setNoteContent] = useState('');

  // Edit mode state
  const [editing, setEditing] = useState(false);
  const [editTlp, setEditTlp] = useState<TLPLevel>('clear');
  const [editConfidence, setEditConfidence] = useState('50');
  const [editCategory, setEditCategory] = useState('');
  const [editDescription, setEditDescription] = useState('');

  // Tag management state
  const [showTagInput, setShowTagInput] = useState(false);
  const [newTag, setNewTag] = useState('');

  // Linked threat actors & campaigns
  const { data: linkedActors = [] } = useThreatActorsForObservable(id || '');
  const { data: linkedCampaigns = [] } = useCampaignsForObservable(id || '');

  // Copy to clipboard state
  const [copied, setCopied] = useState(false);

  const startEditing = () => {
    if (observable) {
      setEditTlp(observable.tlp);
      setEditConfidence(observable.confidence_score.toString());
      setEditCategory(observable.category || '');
      setEditDescription(observable.description || '');
      setEditing(true);
    }
  };

  const handleSave = () => {
    if (!id) return;
    updateMutation.mutate(
      {
        id,
        data: {
          tlp: editTlp,
          confidence_score: parseInt(editConfidence, 10),
          category: editCategory || undefined,
          description: editDescription || undefined,
        },
      },
      {
        onSuccess: () => setEditing(false),
      }
    );
  };

  const handleDelete = () => {
    if (!id) return;
    if (window.confirm('Are you sure you want to delete this observable?')) {
      deleteMutation.mutate(id, {
        onSuccess: () => navigate('/observables'),
      });
    }
  };

  const handleCopy = async () => {
    if (!observable) return;
    try {
      await navigator.clipboard.writeText(observable.value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      addToast('Copied to clipboard', 'success');
    } catch {
      addToast('Failed to copy to clipboard', 'error');
    }
  };

  const handleSearchRelated = () => {
    if (!observable) return;
    navigate(`/search?q=${encodeURIComponent(observable.value)}`);
  };

  const handleAddTag = () => {
    if (!id || !observable || !newTag.trim()) return;
    const updatedTags = [...observable.tags, newTag.trim()];
    updateMutation.mutate(
      { id, data: { tags: updatedTags } },
      {
        onSuccess: () => {
          setNewTag('');
          setShowTagInput(false);
        },
      }
    );
  };

  const handleRemoveTag = (tagToRemove: string) => {
    if (!id || !observable) return;
    const updatedTags = observable.tags.filter((t) => t !== tagToRemove);
    updateMutation.mutate({ id, data: { tags: updatedTags } });
  };

  const handleSubmitNote = () => {
    if (!id || !noteContent.trim()) return;
    createNoteMutation.mutate(
      { observableId: id, data: { content: noteContent.trim() } },
      {
        onSuccess: () => setNoteContent(''),
      }
    );
  };

  const handleDeleteNote = (noteId: string) => {
    if (!id) return;
    deleteNoteMutation.mutate({ observableId: id, noteId });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error || !observable) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-lg text-muted-foreground">Observable not found</p>
        <Button variant="outline" onClick={() => navigate('/observables')}>
          Back to Observables
        </Button>
      </div>
    );
  }

  const sortedNotes = [...notes].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="space-y-6">
      {/* Breadcrumb & Header */}
      <div className="space-y-4">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link
            to="/observables"
            className="hover:text-foreground transition-colors"
          >
            Observables
          </Link>
          <span>/</span>
          <span className="text-foreground font-medium truncate max-w-[400px]">
            {observable.value}
          </span>
        </nav>

        {/* Header with confidence and actions */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-6 min-w-0">
            {/* Confidence Score - large display */}
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-4xl font-bold tabular-nums">
                {observable.confidence_score}
              </span>
              <div className="flex flex-col gap-1">
                <span className="text-sm text-muted-foreground">/ 100</span>
                <ConfidenceMeter
                  value={observable.confidence_score}
                  size="md"
                  showLabel={false}
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ObservableBadge type={observable.type} />
              <Badge
                variant="outline"
                className={TLP_COLORS[observable.tlp] || ''}
              >
                TLP:{observable.tlp.toUpperCase()}
              </Badge>
            </div>
          </div>

          {/* Action buttons */}
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
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditing(false)}
                >
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
      </div>

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* LEFT COLUMN - 3/5 width */}
        <div className="lg:col-span-3 space-y-6">
          {/* Description Section */}
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
                <p className={observable.description ? 'text-sm' : 'text-sm text-muted-foreground italic'}>
                  {observable.description || 'No description'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Value Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Value</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <code className="flex-1 rounded-md bg-muted px-4 py-3 text-sm font-mono break-all">
                  {observable.value}
                </code>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopy}
                  className="shrink-0"
                >
                  {copied ? 'Copied' : 'Copy'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSearchRelated}
                  className="shrink-0"
                >
                  Search Related
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Details Grid */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Details</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
                    Type
                  </p>
                  <p className="text-sm font-medium">{observable.type}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
                    First Seen
                  </p>
                  <p className="text-sm font-medium">
                    {observable.first_seen
                      ? formatDate(observable.first_seen)
                      : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
                    Last Seen
                  </p>
                  <p className="text-sm font-medium">
                    {observable.last_seen
                      ? formatDate(observable.last_seen)
                      : 'N/A'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Relationships */}
          <RelationshipPanel observableId={id!} />
          <RelationshipGraph observableId={id!} />

          {/* Enrichment */}
          <EnrichmentPanel observableId={id!} observableType={observable.type} />

          {/* ATT&CK Techniques */}
          <AttackTechniquesPanel observableId={id!} />

          {/* Linked Threat Actors */}
          {linkedActors.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  Threat Actors ({linkedActors.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {linkedActors.map((actor) => (
                    <Link
                      key={actor.id}
                      to={`/threat-actors/${actor.id}`}
                      className="flex items-center justify-between rounded-md border border-border p-2.5 hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{actor.name}</span>
                        {actor.country && (
                          <Badge variant="outline" className="text-xs">
                            {actor.country}
                          </Badge>
                        )}
                      </div>
                      {actor.motivation && (
                        <span className="text-xs text-muted-foreground capitalize">
                          {actor.motivation}
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Linked Campaigns */}
          {linkedCampaigns.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  Campaigns ({linkedCampaigns.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {linkedCampaigns.map((campaign) => (
                    <Link
                      key={campaign.id}
                      to={`/campaigns/${campaign.id}`}
                      className="flex items-center justify-between rounded-md border border-border p-2.5 hover:bg-accent/50 transition-colors"
                    >
                      <span className="text-sm font-medium">{campaign.name}</span>
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
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Labels/Tags Section */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Labels</CardTitle>
                {!showTagInput && canEdit(user) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowTagInput(true)}
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                  >
                    +
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-center gap-2">
                {observable.tags.length > 0 ? (
                  observable.tags.map((tag) => (
                    <Badge
                      key={tag}
                      variant="secondary"
                      className="gap-1 pr-1"
                    >
                      {tag}
                      {canEdit(user) && (
                        <button
                          onClick={() => handleRemoveTag(tag)}
                          className="ml-1 rounded-full hover:bg-foreground/10 h-4 w-4 inline-flex items-center justify-center text-xs"
                          aria-label={`Remove tag ${tag}`}
                        >
                          x
                        </button>
                      )}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground italic">
                    No labels
                  </span>
                )}
              </div>
              {showTagInput && (
                <div className="flex items-center gap-2 mt-3">
                  <Input
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    placeholder="Add a label..."
                    className="h-8 text-sm"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleAddTag();
                      if (e.key === 'Escape') {
                        setShowTagInput(false);
                        setNewTag('');
                      }
                    }}
                    autoFocus
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAddTag}
                    disabled={!newTag.trim()}
                    className="h-8"
                  >
                    Add
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowTagInput(false);
                      setNewTag('');
                    }}
                    className="h-8"
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* External References Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">External References</CardTitle>
            </CardHeader>
            <CardContent>
              {observable.external_references &&
              observable.external_references.length > 0 ? (
                <div className="space-y-3">
                  {observable.external_references.map((ref, idx) => (
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
                <p className="text-sm text-muted-foreground italic">
                  No external references
                </p>
              )}
            </CardContent>
          </Card>

          {/* Notes Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Notes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Write a note */}
              {canEdit(user) && (
                <div className="space-y-2">
                  <textarea
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[80px] resize-y"
                    placeholder="Write a note..."
                    value={noteContent}
                    onChange={(e) => setNoteContent(e.target.value)}
                  />
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      onClick={handleSubmitNote}
                      disabled={
                        !noteContent.trim() || createNoteMutation.isPending
                      }
                    >
                      {createNoteMutation.isPending ? 'Submitting...' : 'Submit'}
                    </Button>
                  </div>
                </div>
              )}

              {/* Notes list */}
              {sortedNotes.length > 0 ? (
                <div className="space-y-3 border-t border-border pt-4">
                  {sortedNotes.map((note) => (
                    <div
                      key={note.id}
                      className="rounded-md border border-border p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">
                            {note.author.username}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {formatRelativeTime(note.created_at)}
                          </span>
                        </div>
                        {user && isAnalyst(user) && user.id === note.author.id && (
                          <button
                            onClick={() => handleDeleteNote(note.id)}
                            className="text-muted-foreground hover:text-destructive transition-colors p-1"
                            aria-label="Delete note"
                            disabled={deleteNoteMutation.isPending}
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
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                              <line x1="10" y1="11" x2="10" y2="17" />
                              <line x1="14" y1="11" x2="14" y2="17" />
                            </svg>
                          </button>
                        )}
                      </div>
                      <p className="text-sm whitespace-pre-wrap">
                        {note.content}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic border-t border-border pt-4">
                  No notes yet
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* RIGHT COLUMN - 2/5 width */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Information Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Basic Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {editing ? (
                <>
                  {/* TLP edit */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      TLP Marking
                    </p>
                    <Select
                      value={editTlp}
                      onChange={(e) =>
                        setEditTlp(e.target.value as TLPLevel)
                      }
                    >
                      {TLP_LEVELS.map((tlp) => (
                        <option key={tlp} value={tlp}>
                          TLP:{tlp.toUpperCase()}
                        </option>
                      ))}
                    </Select>
                  </div>

                  {/* Confidence edit */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Confidence
                    </p>
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={editConfidence}
                      onChange={(e) => setEditConfidence(e.target.value)}
                    />
                  </div>

                  {/* Category edit */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Category
                    </p>
                    <Select
                      value={editCategory}
                      onChange={(e) => setEditCategory(e.target.value)}
                    >
                      <option value="">No Category</option>
                      {OBSERVABLE_CATEGORIES.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat.charAt(0).toUpperCase() + cat.slice(1)}
                        </option>
                      ))}
                    </Select>
                  </div>
                </>
              ) : (
                <>
                  {/* TLP Marking */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      TLP Marking
                    </p>
                    <Badge
                      variant="outline"
                      className={TLP_COLORS[observable.tlp] || ''}
                    >
                      TLP:{observable.tlp.toUpperCase()}
                    </Badge>
                  </div>

                  {/* Observable Type */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Observable Type
                    </p>
                    <ObservableBadge type={observable.type} />
                  </div>

                  {/* Category */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Category
                    </p>
                    {observable.category ? (
                      <Badge variant="secondary">
                        {observable.category.charAt(0).toUpperCase() +
                          observable.category.slice(1)}
                      </Badge>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        No category
                      </span>
                    )}
                  </div>

                  {/* Sources */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Sources
                    </p>
                    {observable.sources.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {observable.sources.map((source) => (
                          <Badge key={source.id} variant="secondary">
                            {source.name}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        Manual
                      </span>
                    )}
                  </div>

                  {/* Created */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Platform Creation Date
                    </p>
                    <p className="text-sm">{formatDate(observable.created_at)}</p>
                  </div>

                  {/* Modified */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">
                      Modification Date
                    </p>
                    <p className="text-sm">{formatDate(observable.updated_at)}</p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Context Card */}
          {observable.context &&
            Object.keys(observable.context).length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Context</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="rounded-md bg-muted p-4 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(observable.context, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
        </div>
      </div>
    </div>
  );
}
