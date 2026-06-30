import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import { Sidebar } from './Sidebar';

vi.mock('@/hooks/useDashboard', () => ({
  useDashboard: () => ({ data: { total_observables: 1482930, feeds_enabled: 11, total_feeds: 13 }, isLoading: false }),
}));
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'areyes', role: 'admin' }, logout: vi.fn() }),
}));

describe('Sidebar', () => {
  it('renders brand nav with live counts and user', () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.getByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('1.48M')).toBeTruthy();
    expect(screen.getByText('11/13')).toBeTruthy();
    expect(screen.getByText(/api online/i)).toBeTruthy();
    expect(screen.getByText('admin')).toBeTruthy();
  });
});
