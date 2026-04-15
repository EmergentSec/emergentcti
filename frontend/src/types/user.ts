export type UserRole = 'admin' | 'user'

export interface User {
  id: string
  username: string
  email: string | null
  role: UserRole
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface UserCreate {
  username: string
  password: string
  role?: UserRole
  email?: string
}

export interface UserUpdate {
  role?: UserRole
  is_active?: boolean
  email?: string | null
}

export interface PasswordChange {
  new_password: string
  current_password?: string
}
