import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { EmergentLogo } from '@/components/common/EmergentLogo'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardContent } from '@/components/ui/Card'

export default function LoginPage() {
  const [key, setKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()
  const { toast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!key.trim()) return

    setError('')
    setLoading(true)
    try {
      const success = await login(key.trim())
      if (!success) {
        setError('Invalid API key. Please check and try again.')
        toast('Invalid API key', 'error')
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
                Enter your API key to connect
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="cti_..."
              error={error}
              autoFocus
            />
            <Button
              type="submit"
              disabled={loading || !key.trim()}
              className="w-full"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Validating...
                </span>
              ) : (
                'Connect'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
