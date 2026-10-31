import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppLayout } from './AppLayout';

const auth = vi.hoisted(() => ({ isAdmin: true }));
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { username: 'areyes', role: auth.isAdmin ? 'admin' : 'analyst' },
    isAdmin: auth.isAdmin,
    logout: vi.fn(),
  }),
}));
vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({ preference: 'system', resolvedTheme: 'light', setPreference: vi.fn() }),
}));
vi.mock('@/hooks/useDashboard', () => ({
  useDashboard: () => ({ data: { total_observables: 1482930, feeds_enabled: 11, total_feeds: 13 }, isLoading: false }),
}));

/** Make `(min-width: 1024px)` match or not. */
function setViewport(desktop: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: query.includes('min-width') ? desktop : false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => true,
  })) as unknown as typeof window.matchMedia;
}

const originalMatchMedia = window.matchMedia;
beforeEach(() => {
  auth.isAdmin = true;
  setViewport(true);
});
afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
});

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname + loc.search}</div>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<div>dashboard-page</div>} />
          <Route path="observables" element={<LocationProbe />} />
          <Route path="observables/:id" element={<div>detail-page</div>} />
          <Route path="feeds" element={<div>feeds-page</div>} />
          <Route path="settings" element={<div>settings-page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

const heading = () => screen.getByRole('heading', { level: 1 });

describe('AppLayout page header', () => {
  it.each([
    ['/', 'Dashboard'],
    ['/feeds', 'Feeds'],
    ['/settings', 'Settings'],
    ['/observables', 'Observables'],
    ['/observables/42', 'Observables'],
  ])('renders the title for %s from route meta', (path, title) => {
    renderAt(path);
    expect(heading().textContent).toBe(title);
  });

  it('shows Add Observable for admins and routes to the create dialog', () => {
    renderAt('/feeds');
    fireEvent.click(screen.getByRole('button', { name: /add observable/i }));
    expect(screen.getByTestId('location').textContent).toBe('/observables?create=1');
  });

  it('hides Add Observable for non-admins', () => {
    auth.isAdmin = false;
    renderAt('/');
    expect(screen.queryByRole('button', { name: /add observable/i })).toBeNull();
  });
});

describe('AppLayout sidebar', () => {
  it('collapses and expands the persistent sidebar on desktop', () => {
    renderAt('/');
    const menu = screen.getByRole('button', { name: 'Toggle navigation' });
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeTruthy();
    expect(menu.getAttribute('aria-expanded')).toBe('true');

    fireEvent.click(menu);
    expect(screen.queryByRole('navigation', { name: 'Primary' })).toBeNull();
    expect(menu.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(menu);
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeTruthy();
  });

  it('opens the mobile drawer with the menu button and closes it with Esc', () => {
    setViewport(false);
    renderAt('/feeds');
    const menu = screen.getByRole('button', { name: 'Toggle navigation' });
    expect(screen.queryByRole('dialog', { name: 'Navigation' })).toBeNull();
    expect(menu.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(menu);
    const drawer = screen.getByRole('dialog', { name: 'Navigation' });
    expect(menu.getAttribute('aria-expanded')).toBe('true');
    // Focus moves into the drawer, onto the current page's link.
    expect(drawer.contains(document.activeElement)).toBe(true);
    expect(document.activeElement?.textContent).toContain('Feeds');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Navigation' })).toBeNull();
    expect(document.activeElement).toBe(menu);
  });

  it('closes the mobile drawer from the backdrop, close button and on navigation', () => {
    setViewport(false);
    renderAt('/');
    const menu = screen.getByRole('button', { name: 'Toggle navigation' });

    fireEvent.click(menu);
    fireEvent.click(screen.getByTestId('drawer-backdrop'));
    expect(screen.queryByRole('dialog', { name: 'Navigation' })).toBeNull();

    fireEvent.click(menu);
    fireEvent.click(screen.getByRole('button', { name: 'Close navigation' }));
    expect(screen.queryByRole('dialog', { name: 'Navigation' })).toBeNull();

    fireEvent.click(menu);
    act(() => {
      fireEvent.click(screen.getByRole('link', { name: /settings/i }));
    });
    expect(screen.queryByRole('dialog', { name: 'Navigation' })).toBeNull();
    expect(heading().textContent).toBe('Settings');
  });
});
