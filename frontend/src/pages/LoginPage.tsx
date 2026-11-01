import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { EmergentLogo } from '@/components/common/EmergentLogo'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()
  const { toast } = useToast()

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!username.trim() || !password) return

    setError('')
    setLoading(true)
    try {
      const success = await login({ username: username.trim(), password })
      if (!success) {
        setError('Invalid username or password. Please try again.')
        toast('Invalid credentials', 'error')
      }
    } catch {
      setError('Failed to connect. Is the server running?')
      toast('Connection failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardContent className="p-6 sm:p-8">
          <div className="mb-7 flex flex-col items-center space-y-4">
            <EmergentLogo size={52} />
            <div className="text-center">
              <h1 className="text-2xl font-semibold tracking-tight text-foreground">EmergentCTI</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Sign in to your intelligence workspace
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Username"
              autoComplete="username"
              autoFocus
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Password"
              autoComplete="current-password"
            />
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button
              type="submit"
              variant="brand"
              disabled={loading || !username.trim() || !password}
              className="w-full"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <LoadingSpinner size="sm" />
                  Signing in...
                </span>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
