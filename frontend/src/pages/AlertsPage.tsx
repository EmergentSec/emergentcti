import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { formatDate, formatRelativeTime } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { Pagination } from '@/components/common/Pagination';
import {
  useAlertRules,
  useCreateAlertRule,
  useUpdateAlertRule,
  useDeleteAlertRule,
  useAlertEvents,
  useWebhooks,
} from '@/hooks/useAlerts';
import { useToast } from '@/contexts/ToastContext';
import type { AlertRuleCreate, AlertRuleResponse } from '@/types/alert';

type Tab = 'rules' | 'events';

const OBSERVABLE_TYPES = [
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

const TLP_LEVELS = ['clear', 'green', 'amber', 'amber+strict', 'red'];

function AlertRuleForm({
  rule,
  onClose,
}: {
  rule: AlertRuleResponse | null;
  onClose: () => void;
}) {
  const isEdit = !!rule;
  const createMutation = useCreateAlertRule();
  const updateMutation = useUpdateAlertRule();
  const { data: webhooks = [] } = useWebhooks();
  const { addToast } = useToast();

  const [name, setName] = useState(rule?.name || '');
  const [enabled, setEnabled] = useState(rule?.enabled ?? true);
  const [matchType, setMatchType] = useState(rule?.match_type || '');
  const [valuePattern, setValuePattern] = useState(rule?.match_value_pattern || '');
  const [matchTags, setMatchTags] = useState(rule?.match_tags?.join(', ') || '');
  const [matchTlp, setMatchTlp] = useState(rule?.match_tlp || '');
  const [confidenceMin, setConfidenceMin] = useState(
    rule?.match_confidence_min?.toString() || ''
  );
  const [webhookId, setWebhookId] = useState(
    rule?.notification_channels?.find((c) => c.type === 'webhook')?.webhook_id || ''
  );
  const [cooldownMinutes, setCooldownMinutes] = useState(
    rule?.cooldown_minutes?.toString() || '60'
  );

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    const data: AlertRuleCreate = {
      name,
      enabled,
      match_type: matchType || undefined,
      match_value_pattern: valuePattern || undefined,
      match_tags: matchTags
        ? matchTags.split(',').map((t) => t.trim()).filter(Boolean)
        : undefined,
      match_tlp: matchTlp || undefined,
      match_confidence_min: confidenceMin
        ? parseInt(confidenceMin, 10)
        : undefined,
      notification_channels: webhookId
        ? [{ type: 'webhook', webhook_id: webhookId }]
        : [],
      cooldown_minutes: parseInt(cooldownMinutes, 10) || 60,
    };

    if (isEdit && rule) {
      updateMutation.mutate(
        { id: rule.id, data },
        {
          onSuccess: () => {
            addToast('Alert rule updated', 'success');
            onClose();
          },
          onError: () => addToast('Failed to update alert rule', 'error'),
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => {
          addToast('Alert rule created', 'success');
          onClose();
        },
        onError: () => addToast('Failed to create alert rule', 'error'),
      });
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="rule-name" className="text-sm font-medium">
          Name
        </label>
        <Input
          id="rule-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., High confidence malware"
          required
        />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="rounded border-input"
        />
        Enabled
      </label>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <label htmlFor="rule-match-type" className="text-sm font-medium">
            Match Type
          </label>
          <Select
            id="rule-match-type"
            value={matchType}
            onChange={(e) => setMatchType(e.target.value)}
          >
            <option value="">Any Type</option>
            {OBSERVABLE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-2">
          <label htmlFor="rule-match-tlp" className="text-sm font-medium">
            Match TLP
          </label>
          <Select
            id="rule-match-tlp"
            value={matchTlp}
            onChange={(e) => setMatchTlp(e.target.value)}
          >
            <option value="">Any TLP</option>
            {TLP_LEVELS.map((tlp) => (
              <option key={tlp} value={tlp}>
                TLP:{tlp.toUpperCase()}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="rule-value-pattern" className="text-sm font-medium">
          Value Pattern (regex)
        </label>
        <Input
          id="rule-value-pattern"
          value={valuePattern}
          onChange={(e) => setValuePattern(e.target.value)}
          placeholder="e.g., ^192\.168\."
        />
      </div>

      <div className="space-y-2">
        <label htmlFor="rule-tags" className="text-sm font-medium">
          Match Tags (comma-separated)
        </label>
        <Input
          id="rule-tags"
          value={matchTags}
          onChange={(e) => setMatchTags(e.target.value)}
          placeholder="malware, botnet"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <label htmlFor="rule-confidence" className="text-sm font-medium">
            Min Confidence (0-100)
          </label>
          <Input
            id="rule-confidence"
            type="number"
            min="0"
            max="100"
            value={confidenceMin}
            onChange={(e) => setConfidenceMin(e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="rule-cooldown" className="text-sm font-medium">
            Cooldown (minutes)
          </label>
          <Input
            id="rule-cooldown"
            type="number"
            min="0"
            value={cooldownMinutes}
            onChange={(e) => setCooldownMinutes(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="rule-webhook" className="text-sm font-medium">
          Notification Webhook
        </label>
        <Select
          id="rule-webhook"
          value={webhookId}
          onChange={(e) => setWebhookId(e.target.value)}
        >
          <option value="">None</option>
          {webhooks.map((wh) => (
            <option key={wh.id} value={wh.id}>
              {wh.name}
            </option>
          ))}
        </Select>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending
            ? isEdit
              ? 'Saving...'
              : 'Creating...'
            : isEdit
              ? 'Save Changes'
              : 'Create Rule'}
        </Button>
      </DialogFooter>
    </form>
  );
}

function RulesTab() {
  const { data: rules = [], isLoading } = useAlertRules();
  const deleteMutation = useDeleteAlertRule();
  const updateMutation = useUpdateAlertRule();
  const { addToast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRuleResponse | null>(null);

  const handleCreate = () => {
    setEditingRule(null);
    setDialogOpen(true);
  };

  const handleEdit = (rule: AlertRuleResponse) => {
    setEditingRule(rule);
    setDialogOpen(true);
  };

  const handleDelete = (rule: AlertRuleResponse) => {
    if (window.confirm(`Delete alert rule "${rule.name}"?`)) {
      deleteMutation.mutate(rule.id, {
        onSuccess: () => addToast('Alert rule deleted', 'success'),
        onError: () => addToast('Failed to delete alert rule', 'error'),
      });
    }
  };

  const handleToggleEnabled = (rule: AlertRuleResponse) => {
    updateMutation.mutate(
      { id: rule.id, data: { enabled: !rule.enabled } },
      {
        onSuccess: () =>
          addToast(
            `Rule "${rule.name}" ${!rule.enabled ? 'enabled' : 'disabled'}`,
            'success'
          ),
        onError: () => addToast('Failed to update rule', 'error'),
      }
    );
  };

  const buildConditionsSummary = (rule: AlertRuleResponse): string => {
    const parts: string[] = [];
    if (rule.match_type) parts.push(`type=${rule.match_type}`);
    if (rule.match_value_pattern) parts.push(`pattern=${rule.match_value_pattern}`);
    if (rule.match_tags?.length) parts.push(`tags=${rule.match_tags.join(',')}`);
    if (rule.match_tlp) parts.push(`tlp=${rule.match_tlp}`);
    if (rule.match_confidence_min != null)
      parts.push(`confidence>=${rule.match_confidence_min}`);
    return parts.length > 0 ? parts.join(', ') : 'All observables';
  };

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-muted-foreground">
          {rules.length} alert rule(s) configured
        </p>
        <Button onClick={handleCreate}>+ Create Rule</Button>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground py-8 text-center">
          Loading rules...
        </div>
      ) : rules.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            <p>No alert rules configured yet.</p>
            <p className="text-sm mt-1">
              Create a rule to get notified when matching observables are ingested.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <Card key={rule.id}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{rule.name}</span>
                      <Badge
                        variant={rule.enabled ? 'default' : 'secondary'}
                        className={
                          rule.enabled
                            ? 'bg-green-500/20 text-green-400 border-green-500/30'
                            : ''
                        }
                      >
                        {rule.enabled ? 'Active' : 'Disabled'}
                      </Badge>
                      {rule.notification_channels.length > 0 && (
                        <Badge variant="outline" className="text-xs">
                          {rule.notification_channels.length} channel(s)
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground font-mono">
                      {buildConditionsSummary(rule)}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>
                        Cooldown: {rule.cooldown_minutes}m
                      </span>
                      <span>
                        Last triggered:{' '}
                        {rule.last_triggered_at
                          ? formatRelativeTime(rule.last_triggered_at)
                          : 'Never'}
                      </span>
                      <span>Created: {formatDate(rule.created_at)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleEnabled(rule)}
                    >
                      {rule.enabled ? 'Disable' : 'Enable'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleEdit(rule)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDelete(rule)}
                      disabled={deleteMutation.isPending}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogClose onClose={() => setDialogOpen(false)} />
          <DialogHeader>
            <DialogTitle>
              {editingRule ? 'Edit Alert Rule' : 'Create Alert Rule'}
            </DialogTitle>
          </DialogHeader>
          <AlertRuleForm
            rule={editingRule}
            onClose={() => setDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}

function EventsTab() {
  const [page, setPage] = useState(1);
  const [ruleFilter, setRuleFilter] = useState('');
  const { data: eventsData, isLoading } = useAlertEvents({
    page,
    size: 20,
    rule_id: ruleFilter || undefined,
  });
  const { data: rules = [] } = useAlertRules();

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        <Select
          value={ruleFilter}
          onChange={(e) => {
            setRuleFilter(e.target.value);
            setPage(1);
          }}
          className="w-64"
        >
          <option value="">All Rules</option>
          {rules.map((rule) => (
            <option key={rule.id} value={rule.id}>
              {rule.name}
            </option>
          ))}
        </Select>
        <span className="text-sm text-muted-foreground ml-auto">
          {eventsData?.total ?? 0} event(s)
        </span>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground py-8 text-center">
          Loading events...
        </div>
      ) : !eventsData?.items.length ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No alert events found.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rule</TableHead>
                  <TableHead>Observable</TableHead>
                  <TableHead>Triggered</TableHead>
                  <TableHead>Notification</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {eventsData.items.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="font-medium text-sm">
                      {event.rule_name || event.rule_id}
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/observables/${event.observable_id}`}
                        className="text-primary hover:underline text-sm font-mono"
                      >
                        {event.observable_value || event.observable_id}
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatRelativeTime(event.triggered_at)}
                    </TableCell>
                    <TableCell>
                      {event.notification_sent ? (
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                          Sent
                        </Badge>
                      ) : event.notification_error ? (
                        <Badge
                          variant="destructive"
                          title={event.notification_error}
                        >
                          Failed
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Pending</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {eventsData.pages > 1 && (
            <div className="mt-4">
              <Pagination
                page={eventsData.page}
                totalPages={eventsData.pages}
                onPageChange={setPage}
              />
            </div>
          )}
        </>
      )}
    </>
  );
}

export function AlertsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('rules');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Alerts</h1>
        <p className="text-muted-foreground">
          Manage alert rules and view triggered events
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border">
        {(['rules', 'events'] as Tab[]).map((tab) => (
          <button
            key={tab}
            className={cn(
              'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            )}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'rules' ? 'Rules' : 'Events'}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'rules' ? <RulesTab /> : <EventsTab />}
    </div>
  );
}
