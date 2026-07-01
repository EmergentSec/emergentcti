import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import { Header } from './Header';

const toggle = vi.fn();
vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => ({ theme: 'dark', toggle }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: { username: 'a', role: 'admin' }, logout: vi.fn() }) }));

describe('Header', () => {
  it('shows the page title and toggles theme', () => {
    render(<MemoryRouter initialEntries={['/']}><Header /></MemoryRouter>);
    expect(screen.getByText('Dashboard')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Toggle theme'));
    expect(toggle).toHaveBeenCalled();
  });
});
