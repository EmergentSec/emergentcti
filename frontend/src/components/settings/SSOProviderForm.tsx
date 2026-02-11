import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import { useUpdateSSOConfig, useDeleteSSOConfig } from '@/hooks/useSSO';
import { useToast } from '@/contexts/ToastContext';
import type { SSOProviderResponse, SSOProviderConfigUpdate } from '@/types/sso';

interface SSOProviderFormProps {
  provider: SSOProviderResponse | null;
  providerType: string;
  isNew?: boolean;
  onDeleted?: () => void;
}

const PROVIDER_LABELS: Record<string, string> = {
  azure_ad: 'Azure AD / Microsoft Entra ID',
  google: 'Google Workspace',
  oidc: 'Generic OIDC',
};

function getProviderLabel(providerType: string): string {
  return PROVIDER_LABELS[providerType] || providerType;
}

export function SSOProviderForm({
  provider,
  providerType,
  isNew = false,
  onDeleted,
}: SSOProviderFormProps) {
  const [expanded, setExpanded] = useState(isNew);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [displayName, setDisplayName] = useState(
    provider?.display_name || getProviderLabel(providerType)
  );
  const [enabled, setEnabled] = useState(provider?.enabled ?? true);
  const [clientId, setClientId] = useState(
    provider?.provider_config?.client_id || ''
  );
  const [clientSecret, setClientSecret] = useState('');
  const [tenantId, setTenantId] = useState(
    provider?.provider_config?.tenant_id || ''
  );
  const [issuerUrl, setIssuerUrl] = useState(
    provider?.provider_config?.issuer_url || ''
  );
  const [defaultRole, setDefaultRole] = useState<'admin' | 'analyst' | 'readonly'>(
    provider?.default_role || 'analyst'
  );
  const [allowedDomains, setAllowedDomains] = useState(
    provider?.allowed_domains?.join(', ') || ''
  );
  const [autoCreateUsers, setAutoCreateUsers] = useState(
    provider?.auto_create_users ?? true
  );

  const updateMutation = useUpdateSSOConfig();
  const deleteMutation = useDeleteSSOConfig();
  const { addToast } = useToast();

  const handleSave = async () => {
    const config: SSOProviderConfigUpdate = {
      display_name: displayName,
      enabled,
      client_id: clientId || undefined,
      client_secret: clientSecret || undefined,
      default_role: defaultRole,
      auto_create_users: autoCreateUsers,
      allowed_domains: allowedDomains
        ? allowedDomains.split(',').map((d) => d.trim()).filter(Boolean)
        : undefined,
    };

    if (providerType === 'azure_ad' && tenantId) {
      config.tenant_id = tenantId;
    }
    if (providerType === 'oidc' && issuerUrl) {
      config.issuer_url = issuerUrl;
    }

    try {
      await updateMutation.mutateAsync({
        providerType,
        data: config,
      });
      addToast(`SSO provider "${displayName}" saved successfully`, 'success');
      setClientSecret('');
    } catch {
      addToast('Failed to save SSO provider configuration', 'error');
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(providerType);
      addToast(`SSO provider "${displayName}" deleted`, 'success');
      setConfirmDelete(false);
      onDeleted?.();
    } catch {
      addToast('Failed to delete SSO provider', 'error');
    }
  };

  return (
    <div className="rounded-lg border border-border">
      {/* Collapsed header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 text-left hover:bg-accent/50 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg font-medium text-muted-foreground w-6 text-center">
            {providerType === 'azure_ad' && 'M'}
            {providerType === 'google' && 'G'}
            {providerType === 'oidc' && '\u{1F512}'}
          </span>
          <div>
            <p className="font-medium">
              {provider?.display_name || getProviderLabel(providerType)}
            </p>
            <p className="text-xs text-muted-foreground">{providerType}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {provider ? (
            <Badge
              className={
                enabled
                  ? 'bg-green-500/20 text-green-400 border-green-500/30'
                  : 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30'
              }
            >
              {enabled ? 'Enabled' : 'Disabled'}
            </Badge>
          ) : (
            <Badge variant="secondary">Not Configured</Badge>
          )}
          <span className="text-muted-foreground text-sm">
            {expanded ? '\u25B2' : '\u25BC'}
          </span>
        </div>
      </button>

      {/* Expanded form */}
      {expanded && (
        <div className="border-t border-border p-4 space-y-4">
          {/* Display Name */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Display Name</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Sign in with Microsoft"
            />
          </div>

          {/* Enabled toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Enabled</p>
              <p className="text-xs text-muted-foreground">
                Allow users to sign in with this provider
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={enabled}
              onClick={() => setEnabled(!enabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                enabled ? 'bg-primary' : 'bg-zinc-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Client ID */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Client ID</label>
            <Input
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="OAuth Client ID"
            />
          </div>

          {/* Client Secret */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Client Secret</label>
            <Input
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder={provider ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022 (leave blank to keep current)' : 'OAuth Client Secret'}
            />
          </div>

          {/* Azure AD specific: Tenant ID */}
          {providerType === 'azure_ad' && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Tenant ID</label>
              <Input
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="Azure AD Tenant ID"
              />
              <p className="text-xs text-muted-foreground">
                Found in Azure Portal &gt; Azure Active Directory &gt; Overview
              </p>
            </div>
          )}

          {/* OIDC specific: Issuer URL */}
          {providerType === 'oidc' && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Issuer URL</label>
              <Input
                value={issuerUrl}
                onChange={(e) => setIssuerUrl(e.target.value)}
                placeholder="https://your-idp.example.com"
              />
              <p className="text-xs text-muted-foreground">
                The OIDC issuer URL (must support .well-known/openid-configuration)
              </p>
            </div>
          )}

          {/* Default Role */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Default Role</label>
            <Select
              value={defaultRole}
              onChange={(e) =>
                setDefaultRole(e.target.value as 'admin' | 'analyst' | 'readonly')
              }
            >
              <option value="readonly">Read Only</option>
              <option value="analyst">Analyst</option>
              <option value="admin">Admin</option>
            </Select>
            <p className="text-xs text-muted-foreground">
              Role assigned to new users created via this SSO provider
            </p>
          </div>

          {/* Allowed Domains */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Allowed Domains</label>
            <Input
              value={allowedDomains}
              onChange={(e) => setAllowedDomains(e.target.value)}
              placeholder="example.com, company.org"
            />
            <p className="text-xs text-muted-foreground">
              Comma-separated list of email domains. Leave empty to allow all.
            </p>
          </div>

          {/* Auto Create Users */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Auto-Create Users</p>
              <p className="text-xs text-muted-foreground">
                Automatically create accounts for new SSO users
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={autoCreateUsers}
              onClick={() => setAutoCreateUsers(!autoCreateUsers)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                autoCreateUsers ? 'bg-primary' : 'bg-zinc-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  autoCreateUsers ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-between pt-2 border-t border-border">
            <div>
              {provider && !confirmDelete && (
                <Button
                  variant="ghost"
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                  onClick={() => setConfirmDelete(true)}
                  disabled={deleteMutation.isPending}
                >
                  Delete Provider
                </Button>
              )}
              {confirmDelete && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-red-400">Are you sure?</span>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleDelete}
                    disabled={deleteMutation.isPending}
                  >
                    {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfirmDelete(false)}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </div>
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending || !clientId}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Configuration'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
