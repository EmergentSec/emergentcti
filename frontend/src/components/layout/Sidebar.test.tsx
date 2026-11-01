import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { Sidebar } from './Sidebar';

vi.mock('@/hooks/useDashboard', () => ({
  useDashboard: () => ({ data: { total_observables: 1482930, feeds_enabled: 11, total_feeds: 13 }, isLoading: false }),
}));
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'areyes', role: 'admin' }, logout: vi.fn() }),
}));
vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({ preference: 'system', resolvedTheme: 'dark', setPreference: vi.fn() }),
}));

afterEach(cleanup);

describe('Sidebar', () => {
  it('renders brand nav with live counts and user', () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.getByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('Reports')).toBeTruthy();
    expect(screen.getByText('1.48M')).toBeTruthy();
    expect(screen.getByText('11/13')).toBeTruthy();
    expect(screen.getByText(/api online/i)).toBeTruthy();
    expect(screen.getByText('admin')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
  });

  it('marks the active route with a filled primary item', () => {
    render(<MemoryRouter initialEntries={['/feeds']}><Sidebar /></MemoryRouter>);
    const feeds = screen.getByRole('link', { name: /feeds/i });
    expect(feeds.getAttribute('aria-current')).toBe('page');
    expect(feeds.className).toContain('bg-primary');
    expect(screen.getByRole('link', { name: /dashboard/i }).getAttribute('aria-current')).toBeNull();
  });

  it('always shows the Appearance control in the footer', () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.getByRole('radiogroup', { name: 'Appearance' })).toBeTruthy();
  });
});
