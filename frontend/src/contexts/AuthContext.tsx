import {
  createContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { UserResponse, LoginRequest } from '@/types/auth';
import { login as apiLogin, getMe } from '@/api/auth';

export interface AuthContextValue {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = user !== null;

  const refreshUser = useCallback(async () => {
    try {
      const userData = await getMe();
      setUser(userData);
    } catch {
      setUser(null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }, []);

  useEffect(() => {
    // Handle SSO callback: extract tokens from URL hash fragment
    // The backend redirects to /#access_token=...&refresh_token=...&token_type=bearer&is_new_user=true/false
    const hash = window.location.hash;
    if (hash && hash.includes('access_token=')) {
      const params = new URLSearchParams(hash.substring(1));
      const accessToken = params.get('access_token');
      const refreshTokenValue = params.get('refresh_token');

      if (accessToken && refreshTokenValue) {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshTokenValue);

        // Clear the hash from the URL without triggering a page reload
        window.history.replaceState(
          null,
          '',
          window.location.pathname + window.location.search
        );

        refreshUser().finally(() => setIsLoading(false));
        return;
      }
    }

    const token = localStorage.getItem('access_token');
    if (token) {
      refreshUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [refreshUser]);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      const tokenData = await apiLogin(credentials);
      localStorage.setItem('access_token', tokenData.access_token);
      localStorage.setItem('refresh_token', tokenData.refresh_token);
      await refreshUser();
    },
    [refreshUser]
  );

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated, isLoading, login, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}
