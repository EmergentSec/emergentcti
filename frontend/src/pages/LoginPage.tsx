import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { EmergentLogo } from '@/components/common/EmergentLogo'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardContent } from '@/components/ui/Card'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()
  const { toast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center space-y-4 mb-6">
            <EmergentLogo size={56} className="text-foreground" />
            <div className="text-center">
              <h1 className="text-2xl font-bold text-foreground tracking-tight">EmergentCTI</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Sign in to your account
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              autoFocus
            />
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              error={error}
            />
            <Button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Signing in...
                </span>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
