import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { validateApiKey } from '@/api/auth'

interface AuthContextType {
  isAuthenticated: boolean
  apiKey: string | null
  apiKeyPrefix: string | null
  isLoading: boolean
  login: (key: string) => Promise<boolean>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

function extractPrefix(key: string): string {
  // Show first 8 chars as prefix (e.g. "cti_abc1...")
  return key.length > 8 ? key.substring(0, 8) : key
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKey] = useState<string | null>(() => localStorage.getItem('api_key'))
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  const isAuthenticated = apiKey !== null

  const apiKeyPrefix = apiKey ? extractPrefix(apiKey) : null

  const login = useCallback(async (key: string): Promise<boolean> => {
    const valid = await validateApiKey(key)
    if (valid) {
      localStorage.setItem('api_key', key)
      setApiKey(key)
      navigate('/')
      return true
    }
    return false
  }, [navigate])

  const logout = useCallback(() => {
    localStorage.removeItem('api_key')
    setApiKey(null)
    navigate('/login')
  }, [navigate])

  useEffect(() => {
    // Mark loading as done once we've checked localStorage
    setIsLoading(false)
  }, [])

  useEffect(() => {
    if (!isLoading && !isAuthenticated && location.pathname !== '/login') {
      navigate('/login')
    }
  }, [isAuthenticated, isLoading, location.pathname, navigate])

  return (
    <AuthContext.Provider value={{ isAuthenticated, apiKey, apiKeyPrefix, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
