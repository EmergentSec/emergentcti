import { useState, useCallback, type FormEvent } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useSearch } from '@/hooks/useSearch';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { ObservableBadge } from '@/components/observables/ObservableBadge';
import { ConfidenceMeter } from '@/components/common/ConfidenceMeter';
import { Pagination } from '@/components/common/Pagination';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import {
  formatRelativeTime,
  truncate,
  TLP_COLORS,
} from '@/lib/utils';
import type { ObservableType } from '@/types/observable';

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

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const query = searchParams.get('q') || '';
  const type = (searchParams.get('type') as ObservableType) || '';
  const page = parseInt(searchParams.get('page') || '1', 10);

  const [inputValue, setInputValue] = useState(query);

  const { data, isLoading, isFetching } = useSearch({
    q: query,
    type: type || undefined,
    page,
    size: 20,
  });

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const params = new URLSearchParams();
      if (inputValue) params.set('q', inputValue);
      if (type) params.set('type', type);
      setSearchParams(params, { replace: true });
    },
    [inputValue, type, setSearchParams]
  );

  const updateParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams);
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      if (key !== 'page') {
        params.delete('page');
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Search</h1>
        <p className="text-muted-foreground">
          Search across all observables and threat intelligence
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
            {'\u2315'}
          </span>
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search for IPs, domains, hashes, URLs..."
            className="pl-9"
            autoFocus
          />
        </div>
        <Select
          value={type}
          onChange={(e) => updateParam('type', e.target.value)}
          className="w-40"
        >
          <option value="">All Types</option>
          {OBSERVABLE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
        <Button type="submit" disabled={!inputValue.trim()}>
          Search
        </Button>
      </form>

      {/* Results */}
      {isLoading || isFetching ? (
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner size="lg" />
        </div>
      ) : query && data ? (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {data.total.toLocaleString()} result{data.total !== 1 ? 's' : ''}{' '}
            for &quot;{query}&quot;
          </p>

          {data.hits.length > 0 ? (
            <div className="space-y-3">
              {data.hits.map((hit) => (
                <Card
                  key={hit.id}
                  className="cursor-pointer transition-colors hover:border-primary/30"
                  onClick={() => navigate(`/observables/${hit.id}`)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex items-center gap-2">
                          <ObservableBadge type={hit.type} />
                          <Badge
                            variant="outline"
                            className={TLP_COLORS[hit.tlp] || ''}
                          >
                            TLP:{hit.tlp.toUpperCase()}
                          </Badge>
                          {hit.score && (
                            <span className="text-xs text-muted-foreground">
                              Score: {hit.score.toFixed(2)}
                            </span>
                          )}
                        </div>
                        <p className="font-mono text-sm break-all">
                          {truncate(hit.value, 120)}
                        </p>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span>Source: {hit.source || 'Unknown'}</span>
                          <span>Last seen: {formatRelativeTime(hit.last_seen)}</span>
                        </div>
                        {hit.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {hit.tags.slice(0, 5).map((tag) => (
                              <Badge
                                key={tag}
                                variant="secondary"
                                className="text-xs"
                              >
                                {tag}
                              </Badge>
                            ))}
                            {hit.tags.length > 5 && (
                              <Badge variant="secondary" className="text-xs">
                                +{hit.tags.length - 5}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                      <ConfidenceMeter
                        value={hit.confidence}
                        size="sm"
                        className="shrink-0"
                      />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <span className="text-4xl mb-3">{'\u2315'}</span>
              <p className="text-lg font-medium">No results found</p>
              <p className="text-sm">Try a different search term or filter</p>
            </div>
          )}

          {/* Pagination */}
          {data.total > 20 && (
            <Pagination
              page={page}
              totalPages={Math.ceil(data.total / 20)}
              onPageChange={(p) => updateParam('page', p.toString())}
            />
          )}
        </div>
      ) : (
        !query && (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <span className="text-5xl mb-4">{'\u2315'}</span>
            <p className="text-lg font-medium">Search Threat Intelligence</p>
            <p className="text-sm mt-1">
              Enter an IP, domain, hash, URL, or any indicator to search
            </p>
          </div>
        )
      )}
    </div>
  );
}
