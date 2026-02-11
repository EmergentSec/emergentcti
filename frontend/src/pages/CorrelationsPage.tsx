import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
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
  useCorrelationRules,
  useCreateCorrelationRule,
  useUpdateCorrelationRule,
  useDeleteCorrelationRule,
  useCorrelationEvents,
  useTriggerCorrelationRun,
} from '@/hooks/useCorrelations';
import { useFeeds } from '@/hooks/useFeeds';
import { useThreatActors } from '@/hooks/useThreatActors';
import { useCampaigns } from '@/hooks/useCampaigns';
import { useTechniques } from '@/hooks/useAttack';
import { useToast } from '@/contexts/ToastContext';
import type {
  CorrelationRuleCreate,
  CorrelationRuleResponse,
} from '@/types/correlation';

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

const ACTION_TYPE_LABELS: Record<string, string> = {
  link_threat_actor: 'Link Threat Actor',
  link_campaign: 'Link Campaign',
  map_technique: 'Map ATT&CK Technique',
};

function CorrelationRuleForm({
  rule,
  onClose,
}: {
  rule: CorrelationRuleResponse | null;
  onClose: () => void;
}) {
  const isEdit = !!rule;
  const createMutation = useCreateCorrelationRule();
  const updateMutation = useUpdateCorrelationRule();
  const { data: feeds = [] } = useFeeds();
  const { data: threatActorsData } = useThreatActors();
  const { data: campaignsData } = useCampaigns();
  const { data: techniques = [] } = useTechniques();
  const { addToast } = useToast();

  const threatActors = threatActorsData?.items ?? [];
  const campaigns = campaignsData?.items ?? [];

  const [name, setName] = useState(rule?.name || '');
  const [enabled, setEnabled] = useState(rule?.enabled ?? true);
  const [matchType, setMatchType] = useState(rule?.match_type || '');
  const [valuePattern, setValuePattern] = useState(rule?.match_value_pattern || '');
  const [matchTags, setMatchTags] = useState(rule?.match_tags?.join(', ') || '');
  const [matchTlp, setMatchTlp] = useState(rule?.match_tlp || '');
  const [confidenceMin, setConfidenceMin] = useState(
    rule?.match_confidence_min?.toString() || ''
  );
  const [feedId, setFeedId] = useState(rule?.match_feed_id || '');
  const [actionType, setActionType] = useState<string>(
    rule?.action_type || 'link_threat_actor'
  );
  const [targetThreatActorId, setTargetThreatActorId] = useState(
    rule?.target_threat_actor_id || ''
  );
  const [targetCampaignId, setTargetCampaignId] = useState(
    rule?.target_campaign_id || ''
  );
  const [targetTechniqueId, setTargetTechniqueId] = useState(
    rule?.target_technique_id || ''
  );

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    const data: CorrelationRuleCreate = {
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
      match_feed_id: feedId || undefined,
      action_type: actionType as CorrelationRuleCreate['action_type'],
      target_threat_actor_id:
        actionType === 'link_threat_actor' && targetThreatActorId
          ? targetThreatActorId
          : undefined,
      target_campaign_id:
        actionType === 'link_campaign' && targetCampaignId
          ? targetCampaignId
          : undefined,
      target_technique_id:
        actionType === 'map_technique' && targetTechniqueId
          ? targetTechniqueId
          : undefined,
    };

    if (isEdit && rule) {
      updateMutation.mutate(
        { id: rule.id, data },
        {
          onSuccess: () => {
            addToast('Correlation rule updated', 'success');
            onClose();
          },
          onError: () => addToast('Failed to update correlation rule', 'error'),
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => {
          addToast('Correlation rule created', 'success');
          onClose();
        },
        onError: () => addToast('Failed to create correlation rule', 'error'),
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
          placeholder="e.g., Link APT29 IPs"
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

      {/* Match Conditions */}
      <div className="space-y-3 rounded-md border border-border p-3">
        <h4 className="text-sm font-medium text-muted-foreground">
          Match Conditions
        </h4>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <label htmlFor="rule-match-type" className="text-sm font-medium">
              Observable Type
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
              TLP
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
            Tags (comma-separated)
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
            <label htmlFor="rule-feed" className="text-sm font-medium">
              Feed
            </label>
            <Select
              id="rule-feed"
              value={feedId}
              onChange={(e) => setFeedId(e.target.value)}
            >
              <option value="">Any Feed</option>
              {feeds.map((feed) => (
                <option key={feed.id} value={feed.id}>
                  {feed.name}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </div>

      {/* Action */}
      <div className="space-y-3 rounded-md border border-border p-3">
        <h4 className="text-sm font-medium text-muted-foreground">Action</h4>

        <div className="space-y-2">
          <label htmlFor="rule-action-type" className="text-sm font-medium">
            Action Type
          </label>
          <Select
            id="rule-action-type"
            value={actionType}
            onChange={(e) => setActionType(e.target.value)}
          >
            <option value="link_threat_actor">Link Threat Actor</option>
            <option value="link_campaign">Link Campaign</option>
            <option value="map_technique">Map ATT&CK Technique</option>
          </Select>
        </div>

        {actionType === 'link_threat_actor' && (
          <div className="space-y-2">
            <label
              htmlFor="rule-target-actor"
              className="text-sm font-medium"
            >
              Target Threat Actor
            </label>
            <Select
              id="rule-target-actor"
              value={targetThreatActorId}
              onChange={(e) => setTargetThreatActorId(e.target.value)}
            >
              <option value="">Select a threat actor...</option>
              {threatActors.map((actor) => (
                <option key={actor.id} value={actor.id}>
                  {actor.name}
                </option>
              ))}
            </Select>
          </div>
        )}

        {actionType === 'link_campaign' && (
          <div className="space-y-2">
            <label
              htmlFor="rule-target-campaign"
              className="text-sm font-medium"
            >
              Target Campaign
            </label>
            <Select
              id="rule-target-campaign"
              value={targetCampaignId}
              onChange={(e) => setTargetCampaignId(e.target.value)}
            >
              <option value="">Select a campaign...</option>
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </option>
              ))}
            </Select>
          </div>
        )}

        {actionType === 'map_technique' && (
          <div className="space-y-2">
            <label
              htmlFor="rule-target-technique"
              className="text-sm font-medium"
            >
              Target ATT&CK Technique
            </label>
            <Select
              id="rule-target-technique"
              value={targetTechniqueId}
              onChange={(e) => setTargetTechniqueId(e.target.value)}
            >
              <option value="">Select a technique...</option>
              {techniques.map((tech) => (
                <option key={tech.id} value={tech.id}>
                  {tech.external_id} - {tech.name}
                </option>
              ))}
            </Select>
          </div>
        )}
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
  const { data: rules = [], isLoading } = useCorrelationRules();
  const deleteMutation = useDeleteCorrelationRule();
  const updateMutation = useUpdateCorrelationRule();
  const triggerMutation = useTriggerCorrelationRun();
  const { addToast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CorrelationRuleResponse | null>(null);

  const handleCreate = () => {
    setEditingRule(null);
    setDialogOpen(true);
  };

  const handleEdit = (rule: CorrelationRuleResponse) => {
    setEditingRule(rule);
    setDialogOpen(true);
  };

  const handleDelete = (rule: CorrelationRuleResponse) => {
    if (window.confirm(`Delete correlation rule "${rule.name}"?`)) {
      deleteMutation.mutate(rule.id, {
        onSuccess: () => addToast('Correlation rule deleted', 'success'),
        onError: () => addToast('Failed to delete correlation rule', 'error'),
      });
    }
  };

  const handleToggleEnabled = (rule: CorrelationRuleResponse) => {
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

  const handleTriggerRun = () => {
    triggerMutation.mutate(undefined, {
      onSuccess: (data) =>
        addToast(`Correlation run complete: ${data.correlated} correlated`, 'success'),
      onError: () => addToast('Failed to trigger correlation run', 'error'),
    });
  };

  const buildConditionsSummary = (rule: CorrelationRuleResponse): string => {
    const parts: string[] = [];
    if (rule.match_type) parts.push(`type=${rule.match_type}`);
    if (rule.match_value_pattern) parts.push(`pattern=${rule.match_value_pattern}`);
    if (rule.match_tags?.length) parts.push(`tags=${rule.match_tags.join(',')}`);
    if (rule.match_tlp) parts.push(`tlp=${rule.match_tlp}`);
    if (rule.match_confidence_min != null)
      parts.push(`confidence>=${rule.match_confidence_min}`);
    if (rule.match_feed_id) parts.push(`feed=${rule.match_feed_id.slice(0, 8)}...`);
    return parts.length > 0 ? parts.join(', ') : 'All observables';
  };

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-muted-foreground">
          {rules.length} correlation rule(s) configured
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleTriggerRun}
            disabled={triggerMutation.isPending}
          >
            {triggerMutation.isPending ? 'Running...' : 'Run Correlations'}
          </Button>
          <Button onClick={handleCreate}>+ Create Rule</Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground py-8 text-center">
          Loading rules...
        </div>
      ) : rules.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            <p>No correlation rules configured yet.</p>
            <p className="text-sm mt-1">
              Create a rule to automatically link observables to threat actors, campaigns, or ATT&CK techniques.
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
                      <Badge variant="outline" className="text-xs">
                        {ACTION_TYPE_LABELS[rule.action_type] || rule.action_type}
                      </Badge>
                      {rule.target_name && (
                        <Badge variant="outline" className="text-xs">
                          {rule.target_name}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground font-mono">
                      {buildConditionsSummary(rule)}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
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
              {editingRule ? 'Edit Correlation Rule' : 'Create Correlation Rule'}
            </DialogTitle>
          </DialogHeader>
          <CorrelationRuleForm
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
  const { data: eventsData, isLoading } = useCorrelationEvents(page, 20);

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
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
            No correlation events found.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Observable</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Correlated At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {eventsData.items.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell>
                      <Link
                        to={`/observables/${event.observable_id}`}
                        className="text-primary hover:underline text-sm font-mono"
                      >
                        {event.observable_value || event.observable_id}
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm">
                      <Badge variant="outline" className="text-xs">
                        {ACTION_TYPE_LABELS[event.action_type] || event.action_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm font-medium">
                      {event.target_name || event.target_id}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {event.rule_name || event.source}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatRelativeTime(event.correlated_at)}
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

export function CorrelationsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('rules');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Correlations</h1>
        <p className="text-muted-foreground">
          Auto-correlate observables with threat actors, campaigns, and ATT&CK techniques
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
