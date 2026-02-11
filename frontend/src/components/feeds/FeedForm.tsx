import { useState, useEffect, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import type { AuthType, FeedCreateRequest, FeedResponse, FeedType } from '@/types/feed';
import { FEED_PRESETS, type FeedPreset, type PresetAdvancedOption } from '@/data/feedPresets';

interface FeedFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: FeedCreateRequest) => void;
  initialData?: FeedResponse | null;
  isSubmitting?: boolean;
}

function intervalToCron(minutes: number): string {
  if (minutes < 60) {
    return `*/${minutes} * * * *`;
  }
  const hours = Math.floor(minutes / 60);
  return `0 */${hours} * * *`;
}

function cronToInterval(cron: string | null): string {
  if (!cron) return '60';
  const parts = cron.split(' ');
  if (parts.length !== 5) return '60';
  const minMatch = parts[0].match(/^\*\/(\d+)$/);
  if (minMatch) return minMatch[1];
  const hourMatch = parts[1].match(/^\*\/(\d+)$/);
  if (hourMatch) return String(parseInt(hourMatch[1], 10) * 60);
  return '60';
}

const PRESETS_WITH_AUTH = FEED_PRESETS.filter((p) => p.requiresAuth);
const PRESETS_NO_AUTH = FEED_PRESETS.filter((p) => !p.requiresAuth);

function applyAdvancedOptions(
  template: Omit<FeedCreateRequest, 'auth_config'>,
  options: PresetAdvancedOption[],
  values: Record<string, string | number>,
): Omit<FeedCreateRequest, 'auth_config'> {
  const result = JSON.parse(JSON.stringify(template)) as Record<string, unknown>;

  for (const opt of options) {
    const val = values[opt.key] ?? opt.defaultValue;
    const path = opt.templatePath;

    if (path.startsWith('url_param.')) {
      // Append as URL query parameter
      const paramName = path.replace('url_param.', '');
      const url = new URL(result.url as string);
      url.searchParams.set(paramName, String(val));
      result.url = url.toString();
    } else {
      // Set value at dot-path (e.g., 'config.pagination.page_size')
      const parts = path.split('.');
      let current: Record<string, unknown> = result;
      for (let i = 0; i < parts.length - 1; i++) {
        if (current[parts[i]] === undefined || current[parts[i]] === null) {
          current[parts[i]] = {};
        }
        current = current[parts[i]] as Record<string, unknown>;
      }
      current[parts[parts.length - 1]] = typeof opt.defaultValue === 'number' ? Number(val) : val;
    }
  }

  return result as Omit<FeedCreateRequest, 'auth_config'>;
}

export function FeedForm({
  open,
  onOpenChange,
  onSubmit,
  initialData,
  isSubmitting,
}: FeedFormProps) {
  const isEditing = !!initialData;

  // ── Preset mode state ──
  const [selectedPresetId, setSelectedPresetId] = useState<string>('');
  const [presetApiKey, setPresetApiKey] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedValues, setAdvancedValues] = useState<Record<string, string | number>>({});
  const [presetSchedule, setPresetSchedule] = useState('');

  // ── Custom/edit form state ──
  const [name, setName] = useState(initialData?.name || '');
  const [description, setDescription] = useState(initialData?.description || '');
  const [feedType, setFeedType] = useState<FeedType>(initialData?.feed_type || 'api');
  const [url, setUrl] = useState(initialData?.url || '');
  const [intervalMinutes, setIntervalMinutes] = useState(
    cronToInterval(initialData?.schedule_cron ?? null)
  );
  const [enabled, setEnabled] = useState(initialData?.enabled ?? true);
  const [defaultTtlDays, setDefaultTtlDays] = useState(
    initialData?.default_ttl_days?.toString() || ''
  );
  const [defaultConfidence, setDefaultConfidence] = useState(
    initialData?.config?.default_confidence?.toString() || ''
  );
  const [authType, setAuthType] = useState<AuthType>('none');
  const [bearerToken, setBearerToken] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiKeyHeader, setApiKeyHeader] = useState('X-API-Key');
  const [basicUsername, setBasicUsername] = useState('');
  const [basicPassword, setBasicPassword] = useState('');
  const [changingCredentials, setChangingCredentials] = useState(false);

  const hasExistingAuth =
    !!initialData?.config?.auth_type && initialData.config.auth_type !== 'none';

  // Reset all state when dialog opens/closes or initialData changes
  useEffect(() => {
    setSelectedPresetId('');
    setPresetApiKey('');
    setShowAdvanced(false);
    setAdvancedValues({});
    setPresetSchedule('');
    setName(initialData?.name || '');
    setDescription(initialData?.description || '');
    setFeedType(initialData?.feed_type || 'api');
    setUrl(initialData?.url || '');
    setIntervalMinutes(cronToInterval(initialData?.schedule_cron ?? null));
    setEnabled(initialData?.enabled ?? true);
    setDefaultTtlDays(initialData?.default_ttl_days?.toString() || '');
    setDefaultConfidence(initialData?.config?.default_confidence?.toString() || '');
    setAuthType((initialData?.config?.auth_type as AuthType) || 'none');
    setBearerToken('');
    setApiKey('');
    setApiKeyHeader('X-API-Key');
    setBasicUsername('');
    setBasicPassword('');
    setChangingCredentials(false);
  }, [initialData, open]);

  const selectedPreset: FeedPreset | undefined = FEED_PRESETS.find(
    (p) => p.id === selectedPresetId
  );
  const showCustomForm = isEditing || selectedPresetId === '__custom__';

  // ── Preset submission ──
  const handlePresetSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!selectedPreset) return;

    // Apply advanced options to template
    let template = selectedPreset.template;
    if (selectedPreset.advancedOptions) {
      template = applyAdvancedOptions(template, selectedPreset.advancedOptions, advancedValues);
    }

    let feedUrl = template.url;
    let authConfig: Record<string, unknown> | null = null;

    if (selectedPreset.requiresAuth && presetApiKey) {
      if (selectedPreset.authHeaderName === '__url_param__') {
        feedUrl = feedUrl.replace('{API_KEY}', presetApiKey);
      } else {
        authConfig = {
          api_key: presetApiKey,
          api_key_header: selectedPreset.authHeaderName,
        };
      }
    }

    // Apply schedule override
    const finalTemplate = { ...template, url: feedUrl };
    if (presetSchedule) {
      finalTemplate.schedule_cron = presetSchedule;
    }

    onSubmit({
      ...finalTemplate,
      auth_config: authConfig,
    });
  };

  // ── Custom/edit form submission ──
  const handleCustomSubmit = (e: FormEvent) => {
    e.preventDefault();

    const config: Record<string, unknown> = {};
    if (defaultConfidence) {
      config.default_confidence = parseInt(defaultConfidence, 10);
    }
    let authConfig: Record<string, unknown> | null = null;
    let includeAuth = true;

    if (isEditing && hasExistingAuth && !changingCredentials) {
      // Don't include auth_config at all — backend preserves existing encrypted auth
      includeAuth = false;
      // Keep the auth_type in config so the UI still knows the feed uses auth
      config.auth_type = authType;
    } else if (authType !== 'none') {
      config.auth_type = authType;
      switch (authType) {
        case 'bearer':
          authConfig = { token: bearerToken };
          break;
        case 'api_key':
          authConfig = { api_key: apiKey, api_key_header: apiKeyHeader };
          break;
        case 'basic':
          authConfig = { username: basicUsername, password: basicPassword };
          break;
      }
    }

    const minutes = parseInt(intervalMinutes, 10) || 60;

    const ttlValue = defaultTtlDays ? parseInt(defaultTtlDays, 10) : null;

    const payload: Record<string, unknown> = {
      name,
      description: description || undefined,
      feed_type: feedType,
      url,
      schedule_cron: intervalToCron(minutes),
      enabled,
      config,
      default_ttl_days: ttlValue,
    };

    if (includeAuth) {
      payload.auth_config = authConfig;
    }

    onSubmit(payload as unknown as FeedCreateRequest);
  };

  // ── Preset selection view (create mode only) ──
  const renderPresetView = () => (
    <form onSubmit={handlePresetSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="feed-preset" className="text-sm font-medium">
          Feed Source
        </label>
        <Select
          id="feed-preset"
          value={selectedPresetId}
          onChange={(e) => {
            setSelectedPresetId(e.target.value);
            setPresetApiKey('');
          }}
        >
          <option value="">Select a feed...</option>
          <optgroup label="No API Key Required">
            {PRESETS_NO_AUTH.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </optgroup>
          <optgroup label="API Key Required">
            {PRESETS_WITH_AUTH.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </optgroup>
          <optgroup label="Other">
            <option value="__custom__">Custom (manual setup)</option>
          </optgroup>
        </Select>
      </div>

      {selectedPreset && (
        <>
          {/* Preset info */}
          <div className="rounded-lg border bg-muted/50 p-3 space-y-2">
            <p className="text-sm text-muted-foreground">
              {selectedPreset.description}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {selectedPreset.observableTypes.map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className="text-xs font-mono"
                >
                  {t}
                </Badge>
              ))}
            </div>
          </div>

          {/* API key input (only if required) */}
          {selectedPreset.requiresAuth && (
            <div className="space-y-2">
              <label htmlFor="preset-api-key" className="text-sm font-medium">
                {selectedPreset.authLabel || 'API Key'}
              </label>
              <Input
                id="preset-api-key"
                type="password"
                autoComplete="off"
                value={presetApiKey}
                onChange={(e) => setPresetApiKey(e.target.value)}
                placeholder={selectedPreset.authPlaceholder || 'Enter API key'}
                required
              />
            </div>
          )}
        </>
      )}

      {/* Advanced Options */}
      {selectedPreset?.advancedOptions && selectedPreset.advancedOptions.length > 0 && (
        <div className="space-y-3">
          <button
            type="button"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            <span className="text-xs">{showAdvanced ? '\u25BC' : '\u25B6'}</span>
            Advanced Options
          </button>
          {showAdvanced && (
            <div className="space-y-3 rounded-lg border bg-muted/30 p-3">
              {selectedPreset.advancedOptions.map((opt) => (
                <div key={opt.key} className="space-y-1">
                  <label htmlFor={`adv-${opt.key}`} className="text-sm font-medium">
                    {opt.label}
                  </label>
                  {opt.type === 'select' ? (
                    <Select
                      id={`adv-${opt.key}`}
                      value={String(advancedValues[opt.key] ?? opt.defaultValue)}
                      onChange={(e) => setAdvancedValues((prev) => ({ ...prev, [opt.key]: e.target.value }))}
                    >
                      {opt.options?.map((o) => (
                        <option key={String(o.value)} value={String(o.value)}>
                          {o.label}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Input
                      id={`adv-${opt.key}`}
                      type={opt.type}
                      placeholder={opt.placeholder}
                      value={advancedValues[opt.key] ?? opt.defaultValue}
                      onChange={(e) =>
                        setAdvancedValues((prev) => ({
                          ...prev,
                          [opt.key]: opt.type === 'number' ? Number(e.target.value) : e.target.value,
                        }))
                      }
                    />
                  )}
                  {opt.helpText && (
                    <p className="text-xs text-muted-foreground">{opt.helpText}</p>
                  )}
                </div>
              ))}
              {/* Schedule override */}
              <div className="space-y-1">
                <label htmlFor="adv-schedule" className="text-sm font-medium">
                  Schedule
                </label>
                <Select
                  id="adv-schedule"
                  value={presetSchedule}
                  onChange={(e) => setPresetSchedule(e.target.value)}
                >
                  <option value="">Default ({selectedPreset.template.schedule_cron})</option>
                  <option value="0 * * * *">Every hour</option>
                  <option value="0 */4 * * *">Every 4 hours</option>
                  <option value="0 */6 * * *">Every 6 hours</option>
                  <option value="0 */12 * * *">Every 12 hours</option>
                  <option value="0 0 * * *">Daily</option>
                </Select>
                <p className="text-xs text-muted-foreground">How often to pull new data</p>
              </div>
            </div>
          )}
        </div>
      )}

      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={() => onOpenChange(false)}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={
            isSubmitting ||
            !selectedPreset ||
            (selectedPreset.requiresAuth && !presetApiKey)
          }
        >
          {isSubmitting ? 'Creating...' : 'Create Feed'}
        </Button>
      </DialogFooter>
    </form>
  );

  // ── Custom / edit form view ──
  const renderCustomForm = () => (
    <form onSubmit={handleCustomSubmit} className="space-y-4">
      {!isEditing && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-xs text-muted-foreground"
          onClick={() => setSelectedPresetId('')}
        >
          {'<-'} Back to presets
        </Button>
      )}

      <div className="space-y-2">
        <label htmlFor="feed-name" className="text-sm font-medium">
          Name
        </label>
        <Input
          id="feed-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Feed name"
          required
        />
      </div>

      <div className="space-y-2">
        <label htmlFor="feed-description" className="text-sm font-medium">
          Description
        </label>
        <Input
          id="feed-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description"
        />
      </div>

      <div className="space-y-2">
        <label htmlFor="feed-type" className="text-sm font-medium">
          Type
        </label>
        <Select
          id="feed-type"
          value={feedType}
          onChange={(e) => setFeedType(e.target.value as FeedType)}
        >
          <option value="api">API</option>
          <option value="taxii">TAXII</option>
          <option value="file">File</option>
          <option value="scraper">Scraper</option>
        </Select>
      </div>

      <div className="space-y-2">
        <label htmlFor="feed-url" className="text-sm font-medium">
          URL
        </label>
        <Input
          id="feed-url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://feeds.example.com/api/v1/indicators"
          required
        />
      </div>

      {isEditing && hasExistingAuth && !changingCredentials ? (
        <div className="space-y-2">
          <label className="text-sm font-medium">Authentication</label>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className="bg-green-500/10 text-green-500 border-green-500/30"
            >
              {authType === 'api_key'
                ? 'API Key'
                : authType === 'bearer'
                  ? 'Bearer Token'
                  : 'Basic Auth'}{' '}
              configured
            </Badge>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setChangingCredentials(true)}
            >
              Change credentials
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label htmlFor="feed-auth-type" className="text-sm font-medium">
                Authentication
              </label>
              {isEditing && hasExistingAuth && changingCredentials && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-auto py-0 px-1 text-xs text-muted-foreground"
                  onClick={() => {
                    setChangingCredentials(false);
                    setAuthType(
                      (initialData?.config?.auth_type as AuthType) || 'none'
                    );
                    setBearerToken('');
                    setApiKey('');
                    setApiKeyHeader('X-API-Key');
                    setBasicUsername('');
                    setBasicPassword('');
                  }}
                >
                  Cancel
                </Button>
              )}
            </div>
            <Select
              id="feed-auth-type"
              value={authType}
              onChange={(e) => setAuthType(e.target.value as AuthType)}
            >
              <option value="none">None</option>
              <option value="bearer">Bearer Token</option>
              <option value="api_key">API Key</option>
              <option value="basic">Basic Auth</option>
            </Select>
          </div>

          {authType === 'bearer' && (
            <div className="space-y-2">
              <label htmlFor="feed-bearer-token" className="text-sm font-medium">
                Bearer Token
              </label>
              <Input
                id="feed-bearer-token"
                type="password"
                autoComplete="off"
                value={bearerToken}
                onChange={(e) => setBearerToken(e.target.value)}
                placeholder="Enter bearer token"
                required
              />
            </div>
          )}

          {authType === 'api_key' && (
            <>
              <div className="space-y-2">
                <label htmlFor="feed-api-key-header" className="text-sm font-medium">
                  Header Name
                </label>
                <Input
                  id="feed-api-key-header"
                  type="text"
                  autoComplete="off"
                  value={apiKeyHeader}
                  onChange={(e) => setApiKeyHeader(e.target.value)}
                  placeholder="X-API-Key"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="feed-api-key" className="text-sm font-medium">
                  API Key
                </label>
                <Input
                  id="feed-api-key"
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter API key"
                  required
                />
              </div>
            </>
          )}

          {authType === 'basic' && (
            <>
              <div className="space-y-2">
                <label htmlFor="feed-basic-username" className="text-sm font-medium">
                  Username
                </label>
                <Input
                  id="feed-basic-username"
                  type="text"
                  autoComplete="off"
                  value={basicUsername}
                  onChange={(e) => setBasicUsername(e.target.value)}
                  placeholder="Enter username"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="feed-basic-password" className="text-sm font-medium">
                  Password
                </label>
                <Input
                  id="feed-basic-password"
                  type="password"
                  autoComplete="off"
                  value={basicPassword}
                  onChange={(e) => setBasicPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                />
              </div>
            </>
          )}
        </>
      )}

      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-2">
          <label htmlFor="feed-interval" className="text-sm font-medium">
            Interval (minutes)
          </label>
          <Input
            id="feed-interval"
            type="number"
            min="1"
            value={intervalMinutes}
            onChange={(e) => setIntervalMinutes(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="feed-ttl" className="text-sm font-medium">
            Default TTL (days)
          </label>
          <Input
            id="feed-ttl"
            type="number"
            min="1"
            value={defaultTtlDays}
            onChange={(e) => setDefaultTtlDays(e.target.value)}
            placeholder="No expiry"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="feed-confidence" className="text-sm font-medium">
            Default Confidence
          </label>
          <Input
            id="feed-confidence"
            type="number"
            min="0"
            max="100"
            value={defaultConfidence}
            onChange={(e) => setDefaultConfidence(e.target.value)}
            placeholder="50"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="feed-enabled"
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="h-4 w-4 rounded border-input bg-background"
        />
        <label htmlFor="feed-enabled" className="text-sm font-medium">
          Enabled
        </label>
      </div>

      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={() => onOpenChange(false)}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? 'Saving...'
            : isEditing
              ? 'Update Feed'
              : 'Create Feed'}
        </Button>
      </DialogFooter>
    </form>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogClose onClose={() => onOpenChange(false)} />
        <DialogHeader>
          <DialogTitle>
            {isEditing ? 'Edit Feed' : 'Add New Feed'}
          </DialogTitle>
        </DialogHeader>

        {showCustomForm ? renderCustomForm() : renderPresetView()}
      </DialogContent>
    </Dialog>
  );
}
