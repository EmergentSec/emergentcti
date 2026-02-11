import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useThreatActors, useCreateThreatActor } from '@/hooks/useThreatActors';
import { useAuth } from '@/hooks/useAuth';
import { canEdit } from '@/lib/permissions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { formatDate, TLP_COLORS } from '@/lib/utils';
import type { ThreatActorFilters } from '@/types/threat_actor';

const TLP_LEVELS = ['clear', 'green', 'amber', 'amber+strict', 'red'];

export function ThreatActorsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<ThreatActorFilters>({ page: 1, size: 20 });
  const [nameSearch, setNameSearch] = useState('');
  const { data, isLoading } = useThreatActors(filters);
  const createMutation = useCreateThreatActor();

  // Create dialog state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newAliases, setNewAliases] = useState('');
  const [newCountry, setNewCountry] = useState('');
  const [newMotivation, setNewMotivation] = useState('');
  const [newSophistication, setNewSophistication] = useState('');
  const [newTlp, setNewTlp] = useState('clear');
  const [newDescription, setNewDescription] = useState('');

  const handleSearch = () => {
    setFilters((f) => ({ ...f, page: 1, name: nameSearch || undefined }));
  };

  const handleCreate = () => {
    if (!newName.trim()) return;
    createMutation.mutate(
      {
        name: newName.trim(),
        aliases: newAliases ? newAliases.split(',').map((a) => a.trim()).filter(Boolean) : undefined,
        country: newCountry || undefined,
        motivation: newMotivation || undefined,
        sophistication: newSophistication || undefined,
        tlp: newTlp,
        description: newDescription || undefined,
      },
      {
        onSuccess: () => {
          setShowCreate(false);
          setNewName('');
          setNewAliases('');
          setNewCountry('');
          setNewMotivation('');
          setNewSophistication('');
          setNewTlp('clear');
          setNewDescription('');
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Threat Actors</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track and manage threat actor profiles
          </p>
        </div>
        {canEdit(user) && (
          <Button onClick={() => setShowCreate(true)}>Create Threat Actor</Button>
        )}
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <Input
          placeholder="Search by name..."
          value={nameSearch}
          onChange={(e) => setNameSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="max-w-sm"
        />
        <Button variant="outline" onClick={handleSearch}>
          Search
        </Button>
      </div>

      {/* Create Dialog */}
      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">New Threat Actor</CardTitle>
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
                  placeholder="APT29, Lazarus Group, etc."
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Aliases (comma-separated)
                </label>
                <Input
                  value={newAliases}
                  onChange={(e) => setNewAliases(e.target.value)}
                  placeholder="Cozy Bear, The Dukes"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Country
                </label>
                <Input
                  value={newCountry}
                  onChange={(e) => setNewCountry(e.target.value)}
                  placeholder="RU, CN, IR, etc."
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Motivation
                </label>
                <Select
                  value={newMotivation}
                  onChange={(e) => setNewMotivation(e.target.value)}
                >
                  <option value="">Select motivation</option>
                  <option value="espionage">Espionage</option>
                  <option value="financial">Financial</option>
                  <option value="hacktivism">Hacktivism</option>
                  <option value="destruction">Destruction</option>
                  <option value="unknown">Unknown</option>
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  Sophistication
                </label>
                <Select
                  value={newSophistication}
                  onChange={(e) => setNewSophistication(e.target.value)}
                >
                  <option value="">Select sophistication</option>
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
                <label className="text-xs text-muted-foreground uppercase tracking-wider">
                  TLP
                </label>
                <Select
                  value={newTlp}
                  onChange={(e) => setNewTlp(e.target.value)}
                >
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
                Description
              </label>
              <textarea
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[80px] resize-y"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Description of the threat actor..."
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
                No threat actors found. Create one to get started.
              </CardContent>
            </Card>
          )}
          {data?.items.map((actor) => (
            <Link key={actor.id} to={`/threat-actors/${actor.id}`} className="block">
              <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm">{actor.name}</span>
                          {actor.country && (
                            <Badge variant="outline" className="text-xs">
                              {actor.country}
                            </Badge>
                          )}
                          <Badge
                            variant="outline"
                            className={TLP_COLORS[actor.tlp] || ''}
                          >
                            TLP:{actor.tlp.toUpperCase()}
                          </Badge>
                        </div>
                        {actor.aliases && actor.aliases.length > 0 && (
                          <div className="flex items-center gap-1.5 mt-1">
                            <span className="text-xs text-muted-foreground">aka:</span>
                            {actor.aliases.slice(0, 3).map((alias) => (
                              <Badge key={alias} variant="secondary" className="text-xs">
                                {alias}
                              </Badge>
                            ))}
                            {actor.aliases.length > 3 && (
                              <span className="text-xs text-muted-foreground">
                                +{actor.aliases.length - 3} more
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-6 shrink-0 text-xs text-muted-foreground">
                      {actor.motivation && (
                        <div>
                          <span className="uppercase tracking-wider block">Motivation</span>
                          <span className="text-foreground capitalize">{actor.motivation}</span>
                        </div>
                      )}
                      {actor.sophistication && (
                        <div>
                          <span className="uppercase tracking-wider block">Sophistication</span>
                          <span className="text-foreground capitalize">{actor.sophistication}</span>
                        </div>
                      )}
                      <div>
                        <span className="uppercase tracking-wider block">First Seen</span>
                        <span className="text-foreground">
                          {actor.first_seen ? formatDate(actor.first_seen) : 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="uppercase tracking-wider block">Last Seen</span>
                        <span className="text-foreground">
                          {actor.last_seen ? formatDate(actor.last_seen) : 'N/A'}
                        </span>
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
