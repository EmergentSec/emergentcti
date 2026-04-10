import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { login as apiLogin, logout as apiLogout, getMe } from '@/api/auth'
import type { AuthUser, LoginRequest } from '@/types/auth'

interface AuthContextType {
  user: AuthUser | null
  isAuthenticated: boolean
  isAdmin: boolean
  isLoading: boolean
  login: (credentials: LoginRequest) => Promise<boolean>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  const isAuthenticated = user !== null
  const isAdmin = user?.role === 'admin'

  // On mount: check if we have a valid session by calling /auth/me
  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false))
  }, [])

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated && location.pathname !== '/login') {
      navigate('/login')
    }
  }, [isAuthenticated, isLoading, location.pathname, navigate])

  const login = useCallback(async (credentials: LoginRequest): Promise<boolean> => {
    try {
      const userData = await apiLogin(credentials)
      setUser(userData)
      navigate('/')
      return true
    } catch {
      return false
    }
  }, [navigate])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch {
      // Best effort
    }
    setUser(null)
    navigate('/login')
  }, [navigate])

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isAdmin, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
