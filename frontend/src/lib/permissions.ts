import type { UserResponse } from '@/types/auth';

export function isAdmin(user: UserResponse | null): boolean {
  return user?.role === 'admin';
}

export function isAnalyst(user: UserResponse | null): boolean {
  return user?.role === 'analyst' || user?.role === 'admin';
}

export const canEdit = isAnalyst;
export const canDelete = isAdmin;
export const canManageFeeds = isAdmin;
export const canTriggerFeed = isAnalyst;
export const canManageUsers = isAdmin;
