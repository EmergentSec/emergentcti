import { useState, type FormEvent } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { generateApiKey } from '@/api/auth';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { formatDate } from '@/lib/utils';
import { isAdmin } from '@/lib/permissions';
import { useSSOConfigs } from '@/hooks/useSSO';
import { SSOProviderForm } from '@/components/settings/SSOProviderForm';
import { useEnrichmentConfigs, useUpdateEnrichmentConfig } from '@/hooks/useEnrichment';
import {
  useWebhooks,
  useCreateWebhook,
  useUpdateWebhook,
  useDeleteWebhook,
  useTestWebhook,
} from '@/hooks/useAlerts';
import { useToast } from '@/contexts/ToastContext';
import type { SSOProviderType } from '@/types/sso';
import type { EnrichmentConfigResponse, EnrichmentConfigUpdate } from '@/types/enrichment';
import type { WebhookConfigResponse } from '@/types/alert';

function EnrichmentProviderRow({
  config,
  onSave,
  isSaving,
}: {
  config: EnrichmentConfigResponse;
  onSave: (name: string, updates: EnrichmentConfigUpdate) => void;
  isSaving: boolean;
}) {
  const [enabled, setEnabled] = useState(config.enabled);
  const [autoEnrich, setAutoEnrich] = useState(config.auto_enrich);
  const [apiKey, setApiKey] = useState('');
  const [dirty, setDirty] = useState(false);

  const handleToggleEnabled = (val: boolean) => {
    setEnabled(val);
    setDirty(true);
  };

  const handleToggleAutoEnrich = (val: boolean) => {
    setAutoEnrich(val);
    setDirty(true);
  };

  const handleApiKeyChange = (val: string) => {
    setApiKey(val);
    setDirty(true);
  };

  const handleSave = () => {
    const updates: EnrichmentConfigUpdate = {
      enabled,
      auto_enrich: autoEnrich,
    };
    if (apiKey) {
      updates.api_key = apiKey;
    }
    onSave(config.provider_name, updates);
    setApiKey('');
    setDirty(false);
  };

  return (
    <div className="rounded-md border border-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm capitalize">{config.provider_name}</span>
          {config.has_api_key ? (
            <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
              Key configured
            </Badge>
          ) : (
            <Badge variant="secondary">No API key</Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => handleToggleEnabled(e.target.checked)}
              className="rounded border-input"
            />
            Enabled
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoEnrich}
              onChange={(e) => handleToggleAutoEnrich(e.target.checked)}
              className="rounded border-input"
            />
            Auto-enrich
          </label>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {config.supported_types.map((type) => (
          <Badge key={type} variant="outline" className="text-xs">
            {type}
          </Badge>
        ))}
      </div>

      <div className="space-y-2">
        <label className="text-sm text-muted-foreground">
          API Key {config.has_api_key && '(leave blank to keep current)'}
        </label>
        <Input
          type="password"
          value={apiKey}
          onChange={(e) => handleApiKeyChange(e.target.value)}
          placeholder={config.has_api_key ? 'Key configured' : 'Enter API key...'}
          className="font-mono text-sm"
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          Priority: {config.priority}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSave}
          disabled={!dirty || isSaving}
        >
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </div>
  );
}

const WEBHOOK_EVENTS = [
  { value: 'observable.created', label: 'Observable Created' },
  { value: 'alert.triggered', label: 'Alert Triggered' },
  { value: 'feed.completed', label: 'Feed Completed' },
  { value: 'enrichment.completed', label: 'Enrichment Completed' },
];

function WebhooksSection() {
  const { data: webhooks = [], isLoading } = useWebhooks();
  const createMutation = useCreateWebhook();
  const updateMutation = useUpdateWebhook();
  const deleteMutation = useDeleteWebhook();
  const testMutation = useTestWebhook();
  const { addToast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<WebhookConfigResponse | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formUrl, setFormUrl] = useState('');
  const [formSecret, setFormSecret] = useState('');
  const [formEnabled, setFormEnabled] = useState(true);
  const [formEvents, setFormEvents] = useState<string[]>([]);

  const openCreateDialog = () => {
    setEditingWebhook(null);
    setFormName('');
    setFormUrl('');
    setFormSecret('');
    setFormEnabled(true);
    setFormEvents([]);
    setDialogOpen(true);
  };

  const openEditDialog = (wh: WebhookConfigResponse) => {
    setEditingWebhook(wh);
    setFormName(wh.name);
    setFormUrl(wh.url);
    setFormSecret('');
    setFormEnabled(wh.enabled);
    setFormEvents(wh.events);
    setDialogOpen(true);
  };

  const handleToggleEvent = (event: string) => {
    setFormEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const data = {
      name: formName,
      url: formUrl,
      secret: formSecret || undefined,
      enabled: formEnabled,
      events: formEvents,
    };

    if (editingWebhook) {
      updateMutation.mutate(
        { id: editingWebhook.id, data },
        {
          onSuccess: () => {
            addToast('Webhook updated', 'success');
            setDialogOpen(false);
          },
          onError: () => addToast('Failed to update webhook', 'error'),
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => {
          addToast('Webhook created', 'success');
          setDialogOpen(false);
        },
        onError: () => addToast('Failed to create webhook', 'error'),
      });
    }
  };

  const handleDelete = (wh: WebhookConfigResponse) => {
    if (window.confirm(`Delete webhook "${wh.name}"?`)) {
      deleteMutation.mutate(wh.id, {
        onSuccess: () => addToast('Webhook deleted', 'success'),
        onError: () => addToast('Failed to delete webhook', 'error'),
      });
    }
  };

  const handleTest = (wh: WebhookConfigResponse) => {
    testMutation.mutate(wh.id, {
      onSuccess: (result) => {
        if (result.success) {
          addToast(`Test successful (status ${result.status_code})`, 'success');
        } else {
          addToast(`Test failed: ${result.error || 'Unknown error'}`, 'error');
        }
      },
      onError: () => addToast('Failed to send test', 'error'),
    });
  };

  const handleToggleEnabled = (wh: WebhookConfigResponse) => {
    updateMutation.mutate(
      { id: wh.id, data: { enabled: !wh.enabled } },
      {
        onSuccess: () =>
          addToast(
            `Webhook "${wh.name}" ${!wh.enabled ? 'enabled' : 'disabled'}`,
            'success'
          ),
        onError: () => addToast('Failed to update webhook', 'error'),
      }
    );
  };

  const maskUrl = (url: string): string => {
    try {
      const parsed = new URL(url);
      const host = parsed.hostname;
      if (host.length > 10) {
        return `${parsed.protocol}//${host.slice(0, 6)}...${host.slice(-4)}${parsed.pathname}`;
      }
      return url;
    } catch {
      return url.length > 40 ? url.slice(0, 37) + '...' : url;
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Webhooks</CardTitle>
            <CardDescription>
              Configure webhook endpoints for event notifications
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={openCreateDialog}>
            + Add Webhook
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading webhooks...</p>
        )}

        {!isLoading && webhooks.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No webhooks configured. Click "Add Webhook" to create one.
          </p>
        )}

        {webhooks.map((wh) => (
          <div
            key={wh.id}
            className="rounded-md border border-border p-4 space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{wh.name}</span>
                <Badge
                  variant={wh.enabled ? 'default' : 'secondary'}
                  className={
                    wh.enabled
                      ? 'bg-green-500/20 text-green-400 border-green-500/30'
                      : ''
                  }
                >
                  {wh.enabled ? 'Active' : 'Disabled'}
                </Badge>
                {wh.has_secret && (
                  <Badge variant="outline" className="text-xs">
                    Secret
                  </Badge>
                )}
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={wh.enabled}
                  onChange={() => handleToggleEnabled(wh)}
                  className="rounded border-input"
                />
                Enabled
              </label>
            </div>

            <p className="text-sm text-muted-foreground font-mono">
              {maskUrl(wh.url)}
            </p>

            <div className="flex flex-wrap gap-1.5">
              {wh.events.map((evt) => (
                <Badge key={evt} variant="outline" className="text-xs">
                  {evt}
                </Badge>
              ))}
              {wh.events.length === 0 && (
                <span className="text-xs text-muted-foreground">No events subscribed</span>
              )}
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Created: {formatDate(wh.created_at)}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleTest(wh)}
                  disabled={testMutation.isPending}
                >
                  {testMutation.isPending ? 'Testing...' : 'Test'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => openEditDialog(wh)}
                >
                  Edit
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDelete(wh)}
                  disabled={deleteMutation.isPending}
                >
                  Delete
                </Button>
              </div>
            </div>
          </div>
        ))}
      </CardContent>

      {/* Webhook Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogClose onClose={() => setDialogOpen(false)} />
          <DialogHeader>
            <DialogTitle>
              {editingWebhook ? 'Edit Webhook' : 'Add Webhook'}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="wh-name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="wh-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g., Slack Alerts"
                required
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="wh-url" className="text-sm font-medium">
                URL
              </label>
              <Input
                id="wh-url"
                type="url"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                placeholder="https://hooks.example.com/webhook"
                required
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="wh-secret" className="text-sm font-medium">
                Secret{' '}
                <span className="text-muted-foreground font-normal">
                  (optional{editingWebhook?.has_secret ? ', leave blank to keep' : ''})
                </span>
              </label>
              <Input
                id="wh-secret"
                type="password"
                value={formSecret}
                onChange={(e) => setFormSecret(e.target.value)}
                placeholder={
                  editingWebhook?.has_secret
                    ? 'Secret configured'
                    : 'Optional signing secret'
                }
              />
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={formEnabled}
                onChange={(e) => setFormEnabled(e.target.checked)}
                className="rounded border-input"
              />
              Enabled
            </label>

            <div className="space-y-2">
              <label className="text-sm font-medium">Events</label>
              <div className="space-y-2">
                {WEBHOOK_EVENTS.map((evt) => (
                  <label
                    key={evt.value}
                    className="flex items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={formEvents.includes(evt.value)}
                      onChange={() => handleToggleEvent(evt.value)}
                      className="rounded border-input"
                    />
                    {evt.label}
                    <span className="text-xs text-muted-foreground font-mono">
                      ({evt.value})
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {createMutation.isPending || updateMutation.isPending
                  ? 'Saving...'
                  : editingWebhook
                    ? 'Save Changes'
                    : 'Create Webhook'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [generatingKey, setGeneratingKey] = useState(false);
  const [keyError, setKeyError] = useState('');
  const [copied, setCopied] = useState(false);
  const [addingProvider, setAddingProvider] = useState<SSOProviderType | ''>('');
  const [newProviders, setNewProviders] = useState<SSOProviderType[]>([]);
  const userIsAdmin = isAdmin(user);
  const { data: ssoConfigs, isLoading: ssoLoading } = useSSOConfigs();
  const { data: enrichmentConfigs = [], isLoading: enrichmentLoading } = useEnrichmentConfigs();
  const updateEnrichmentMutation = useUpdateEnrichmentConfig();
  const { addToast } = useToast();

  const handleGenerateApiKey = async () => {
    setGeneratingKey(true);
    setKeyError('');
    try {
      const result = await generateApiKey();
      setApiKey(result.api_key);
      await refreshUser();
    } catch {
      setKeyError('Failed to generate API key');
    } finally {
      setGeneratingKey(false);
    }
  };

  const handleCopyKey = async () => {
    if (apiKey) {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and platform preferences
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Column — Platform Configuration */}
        <div className="space-y-6 lg:col-span-7">
          {/* API Key Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">API Key</CardTitle>
                  <CardDescription>
                    Generate an API key for programmatic access
                  </CardDescription>
                </div>
                {user?.has_api_key ? (
                  <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                    Active
                  </Badge>
                ) : (
                  <Badge variant="secondary">None</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {apiKey && (
                <div className="space-y-2">
                  <p className="text-sm text-amber-400">
                    Save this key now. It will not be shown again.
                  </p>
                  <div className="flex gap-2">
                    <Input
                      value={apiKey}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <Button variant="outline" onClick={handleCopyKey}>
                      {copied ? 'Copied!' : 'Copy'}
                    </Button>
                  </div>
                </div>
              )}

              {keyError && (
                <p className="text-sm text-red-400">{keyError}</p>
              )}

              <Button
                variant="outline"
                onClick={handleGenerateApiKey}
                disabled={generatingKey}
              >
                {generatingKey ? 'Generating...' : 'Generate New API Key'}
              </Button>

              <p className="text-xs text-muted-foreground">
                Generating a new API key will invalidate any existing keys.
              </p>
            </CardContent>
          </Card>

          {/* SSO Providers Card (Admin only) */}
          {userIsAdmin && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">SSO Providers</CardTitle>
                <CardDescription>
                  Configure Single Sign-On providers for your organization
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {ssoLoading && (
                  <p className="text-sm text-muted-foreground">
                    Loading SSO configuration...
                  </p>
                )}

                {/* Existing configured providers */}
                {ssoConfigs?.map((config) => (
                  <SSOProviderForm
                    key={config.provider_type}
                    provider={config}
                    providerType={config.provider_type}
                    onDeleted={() => {
                      setNewProviders((prev) =>
                        prev.filter((p) => p !== config.provider_type)
                      );
                    }}
                  />
                ))}

                {/* Newly added (not yet saved) providers */}
                {newProviders
                  .filter(
                    (pt) => !ssoConfigs?.some((c) => c.provider_type === pt)
                  )
                  .map((pt) => (
                    <SSOProviderForm
                      key={pt}
                      provider={null}
                      providerType={pt}
                      isNew
                      onDeleted={() =>
                        setNewProviders((prev) => prev.filter((p) => p !== pt))
                      }
                    />
                  ))}

                {/* Add Provider */}
                {(() => {
                  const configuredTypes = new Set([
                    ...(ssoConfigs?.map((c) => c.provider_type) || []),
                    ...newProviders,
                  ]);
                  const allTypes: { value: SSOProviderType; label: string }[] = [
                    { value: 'azure_ad', label: 'Azure AD / Microsoft Entra ID' },
                    { value: 'google', label: 'Google Workspace' },
                    { value: 'oidc', label: 'Generic OIDC' },
                  ];
                  const availableTypes = allTypes.filter((t) => !configuredTypes.has(t.value));

                  if (availableTypes.length === 0) return null;

                  return (
                    <div className="flex items-center gap-2 pt-2">
                      <Select
                        value={addingProvider}
                        onChange={(e) =>
                          setAddingProvider(e.target.value as SSOProviderType | '')
                        }
                        className="flex-1"
                      >
                        <option value="">Select a provider to add...</option>
                        {availableTypes.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </Select>
                      <Button
                        variant="outline"
                        disabled={!addingProvider}
                        onClick={() => {
                          if (addingProvider) {
                            setNewProviders((prev) => [...prev, addingProvider as SSOProviderType]);
                            setAddingProvider('');
                          }
                        }}
                      >
                        Add Provider
                      </Button>
                    </div>
                  );
                })()}

                {!ssoLoading &&
                  (!ssoConfigs || ssoConfigs.length === 0) &&
                  newProviders.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      No SSO providers configured. Use the dropdown above to add one.
                    </p>
                  )}
              </CardContent>
            </Card>
          )}

          {/* Enrichment Providers Card (Admin only) */}
          {userIsAdmin && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Enrichment Providers</CardTitle>
                <CardDescription>
                  Configure threat intelligence enrichment providers
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {enrichmentLoading && (
                  <p className="text-sm text-muted-foreground">
                    Loading enrichment configuration...
                  </p>
                )}

                {!enrichmentLoading && enrichmentConfigs.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No enrichment providers available. Providers are registered by the backend.
                  </p>
                )}

                {enrichmentConfigs.map((config) => (
                  <EnrichmentProviderRow
                    key={config.id}
                    config={config}
                    onSave={(name, updates) => {
                      updateEnrichmentMutation.mutate(
                        { name, data: updates },
                        {
                          onSuccess: () => addToast('Provider updated', 'success'),
                          onError: () => addToast('Failed to update provider', 'error'),
                        }
                      );
                    }}
                    isSaving={updateEnrichmentMutation.isPending}
                  />
                ))}
              </CardContent>
            </Card>
          )}

          {/* Webhooks Card (Admin only) */}
          {userIsAdmin && <WebhooksSection />}
        </div>

        {/* Right Column — Account & Preferences */}
        <div className="space-y-6 lg:col-span-5">
          {/* Profile Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Profile</CardTitle>
              <CardDescription>Your account information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Username</p>
                  <p className="font-medium">{user?.username || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Email</p>
                  <p className="font-medium">{user?.email || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Auth Provider</p>
                  <p className="font-medium capitalize">{user?.auth_provider || 'local'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Role</p>
                  <Badge variant="secondary" className="capitalize">
                    {user?.role || 'unknown'}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Member Since</p>
                  <p className="font-medium text-sm">
                    {user?.created_at ? formatDate(user.created_at) : '-'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <div className="flex items-center gap-2">
                    <div
                      className={`h-2 w-2 rounded-full ${user?.is_active ? 'bg-green-500' : 'bg-red-500'}`}
                    />
                    <span className="text-sm font-medium">
                      {user?.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Appearance Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Appearance</CardTitle>
              <CardDescription>Customize the interface</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Theme</p>
                  <p className="text-sm text-muted-foreground">
                    Switch between dark and light mode
                  </p>
                </div>
                <Button variant="outline" onClick={toggleTheme}>
                  {theme === 'dark' ? '\u263C Light Mode' : '\u263E Dark Mode'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* About Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">About</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Platform</span>
                <span className="font-medium">EmergentCTI</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Version</span>
                <span className="font-medium font-mono">0.1.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Frontend</span>
                <span className="font-medium font-mono">React 18 + Vite</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Backend</span>
                <span className="font-medium font-mono">FastAPI + Python</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
