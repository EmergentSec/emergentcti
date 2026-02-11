import { useState, type FormEvent } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { EmergentLogo } from '@/components/common/EmergentLogo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { useSSOProviders } from '@/hooks/useSSO';
import { getSSOAuthorizeUrl } from '@/api/sso';

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [ssoLoading, setSsoLoading] = useState<string | null>(null);
  const { data: ssoProviders } = useSSOProviders();

  if (isLoading) return null;
  if (isAuthenticated) return <Navigate to="/" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      await login({ username, password });
      navigate('/', { replace: true });
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || 'Login failed');
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSSOLogin = async (providerType: string) => {
    setSsoLoading(providerType);
    try {
      const { authorization_url } = await getSSOAuthorizeUrl(providerType);
      window.location.href = authorization_url;
    } catch {
      setError('Failed to initiate SSO login');
      setSsoLoading(null);
    }
  };

  const getSSOIcon = (providerType: string): string => {
    switch (providerType) {
      case 'azure_ad':
        return 'M';
      case 'google':
        return 'G';
      default:
        return '\u{1F512}';
    }
  };

  const getSSOButtonLabel = (provider: { provider_type: string; display_name: string }): string => {
    if (provider.display_name) return provider.display_name;
    switch (provider.provider_type) {
      case 'azure_ad':
        return 'Sign in with Microsoft';
      case 'google':
        return 'Sign in with Google';
      default:
        return 'Sign in with SSO';
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4">
            <EmergentLogo size={56} className="mx-auto text-foreground" />
          </div>
          <h1 className="text-2xl font-bold">EmergentCTI</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cyber Threat Intelligence
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Sign in</CardTitle>
            <CardDescription>
              Enter your credentials to access the platform
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <label htmlFor="username" className="text-sm font-medium">
                  Username
                </label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  autoComplete="username"
                  required
                  autoFocus
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  autoComplete="current-password"
                  required
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={submitting}
              >
                {submitting ? 'Signing in...' : 'Sign in'}
              </Button>
            </form>

            {ssoProviders && ssoProviders.length > 0 && (
              <>
                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-card px-2 text-muted-foreground">
                      or continue with
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  {ssoProviders.map((provider) => (
                    <Button
                      key={provider.provider_type}
                      variant="outline"
                      className="w-full justify-center gap-3"
                      onClick={() => handleSSOLogin(provider.provider_type)}
                      disabled={ssoLoading !== null}
                    >
                      <span className="inline-flex h-5 w-5 items-center justify-center rounded text-xs font-bold bg-muted">
                        {getSSOIcon(provider.provider_type)}
                      </span>
                      {ssoLoading === provider.provider_type
                        ? 'Redirecting...'
                        : getSSOButtonLabel(provider)}
                    </Button>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          EmergentCTI v0.1.0
        </p>
      </div>
    </div>
  );
}
