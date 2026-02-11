import { useState } from 'react';
import { useAuditLogs } from '@/hooks/useAudit';
import { formatDate, cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Link } from 'react-router-dom';

const ACTION_OPTIONS = [
  { value: '', label: 'All Actions' },
  { value: 'create', label: 'Create' },
  { value: 'update', label: 'Update' },
  { value: 'delete', label: 'Delete' },
  { value: 'login', label: 'Login' },
  { value: 'logout', label: 'Logout' },
  { value: 'export', label: 'Export' },
  { value: 'import', label: 'Import' },
  { value: 'enrich', label: 'Enrich' },
];

const ENTITY_TYPE_OPTIONS = [
  { value: '', label: 'All Entity Types' },
  { value: 'observable', label: 'Observable' },
  { value: 'feed', label: 'Feed' },
  { value: 'user', label: 'User' },
  { value: 'alert_rule', label: 'Alert Rule' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'sso_config', label: 'SSO Config' },
  { value: 'enrichment_config', label: 'Enrichment Config' },
  { value: 'threat_actor', label: 'Threat Actor' },
  { value: 'campaign', label: 'Campaign' },
  { value: 'saved_search', label: 'Saved Search' },
];

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-green-500/20 text-green-400',
  update: 'bg-blue-500/20 text-blue-400',
  delete: 'bg-red-500/20 text-red-400',
  login: 'bg-purple-500/20 text-purple-400',
  logout: 'bg-gray-500/20 text-gray-400',
  export: 'bg-amber-500/20 text-amber-400',
  import: 'bg-cyan-500/20 text-cyan-400',
  enrich: 'bg-indigo-500/20 text-indigo-400',
};

function entityLink(entityType: string, entityId: string | null): string | null {
  if (!entityId) return null;
  switch (entityType) {
    case 'observable':
      return `/observables/${entityId}`;
    case 'feed':
      return `/feeds`;
    default:
      return null;
  }
}

export function ActivityPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState('');
  const [entityType, setEntityType] = useState('');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const { data, isLoading } = useAuditLogs({
    page,
    size: 50,
    action: action || undefined,
    entity_type: entityType || undefined,
  });

  const items = data?.items ?? [];
  const totalPages = data?.pages ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Activity Log</h1>
        <p className="text-muted-foreground">
          Audit trail of all system actions
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4">
            <select
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            >
              {ACTION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              value={entityType}
              onChange={(e) => {
                setEntityType(e.target.value);
                setPage(1);
              }}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            >
              {ENTITY_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {data && (
              <span className="ml-auto flex items-center text-sm text-muted-foreground">
                {data.total.toLocaleString()} total entries
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Audit Logs</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 10 }).map((_, i) => (
                <div
                  key={i}
                  className="h-12 animate-pulse rounded bg-muted"
                />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              No audit logs found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">Timestamp</th>
                    <th className="pb-3 pr-4 font-medium">User</th>
                    <th className="pb-3 pr-4 font-medium">Action</th>
                    <th className="pb-3 pr-4 font-medium">Entity Type</th>
                    <th className="pb-3 pr-4 font-medium">Entity ID</th>
                    <th className="pb-3 pr-4 font-medium">IP</th>
                    <th className="pb-3 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const link = entityLink(item.entity_type, item.entity_id);
                    const isExpanded = expandedRow === item.id;
                    return (
                      <tr
                        key={item.id}
                        className="border-b border-border/50 hover:bg-muted/30"
                      >
                        <td className="py-3 pr-4 whitespace-nowrap">
                          {formatDate(item.created_at)}
                        </td>
                        <td className="py-3 pr-4">
                          {item.username ?? (
                            <span className="text-muted-foreground">
                              system
                            </span>
                          )}
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className={cn(
                              'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
                              ACTION_COLORS[item.action] ??
                                'bg-gray-500/20 text-gray-400'
                            )}
                          >
                            {item.action}
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {item.entity_type}
                        </td>
                        <td className="py-3 pr-4 font-mono text-xs">
                          {link ? (
                            <Link
                              to={link}
                              className="text-primary hover:underline"
                            >
                              {item.entity_id?.slice(0, 8)}...
                            </Link>
                          ) : item.entity_id ? (
                            <span title={item.entity_id}>
                              {item.entity_id.slice(0, 8)}...
                            </span>
                          ) : (
                            <span className="text-muted-foreground">--</span>
                          )}
                        </td>
                        <td className="py-3 pr-4 text-xs text-muted-foreground">
                          {item.ip_address ?? '--'}
                        </td>
                        <td className="py-3">
                          {item.details ? (
                            <button
                              onClick={() =>
                                setExpandedRow(isExpanded ? null : item.id)
                              }
                              className="text-xs text-primary hover:underline"
                            >
                              {isExpanded ? 'Hide' : 'Show'}
                            </button>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              --
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Expanded detail rows rendered below the table */}
              {expandedRow &&
                items
                  .filter((item) => item.id === expandedRow && item.details)
                  .map((item) => (
                    <div
                      key={`detail-${item.id}`}
                      className="mt-2 rounded-md border bg-muted/30 p-4"
                    >
                      <pre className="overflow-x-auto text-xs text-muted-foreground">
                        {JSON.stringify(item.details, null, 2)}
                      </pre>
                    </div>
                  ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
