import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import { Header } from './Header';

/** Make the `md` (min-width: 768px) query match (wide) or not (narrow). */
function setWide(wide: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: query.includes('min-width') ? wide : false,
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
beforeEach(() => setWide(true));
afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
});

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname + loc.search}</div>;
}

function renderHeader(props: Partial<Parameters<typeof Header>[0]> = {}) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Header {...props} />
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Header (top bar)', () => {
  it('shows the wordmark and a menu button wired to the sidebar', () => {
    const onMenuClick = vi.fn();
    renderHeader({ onMenuClick, menuExpanded: true, menuControls: 'app-sidebar' });
    expect(screen.getByText('EmergentCTI')).toBeTruthy();
    const menu = screen.getByRole('button', { name: 'Toggle navigation' });
    expect(menu.getAttribute('aria-expanded')).toBe('true');
    expect(menu.getAttribute('aria-controls')).toBe('app-sidebar');
    fireEvent.click(menu);
    expect(onMenuClick).toHaveBeenCalledTimes(1);
  });

  it('no longer renders the binary theme toggle', () => {
    renderHeader();
    expect(screen.queryByLabelText('Toggle theme')).toBeNull();
  });

  it('navigates to the observables search on Enter', () => {
    renderHeader();
    const input = screen.getByRole('searchbox', { name: 'Search observables' });
    fireEvent.change(input, { target: { value: ' 8.8.8.8 ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.getByTestId('location').textContent).toBe('/observables?q=8.8.8.8');
  });

  it('focuses the search field on Ctrl+K and Cmd+K', () => {
    renderHeader();
    const input = screen.getByRole('searchbox', { name: 'Search observables' });
    expect(document.activeElement).not.toBe(input);
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(document.activeElement).toBe(input);
    input.blur();
    fireEvent.keyDown(document, { key: 'K', metaKey: true });
    expect(document.activeElement).toBe(input);
  });

  it('ignores Ctrl+K while a modal dialog is open', () => {
    renderHeader();
    const modal = document.createElement('div');
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    const field = document.createElement('input');
    modal.appendChild(field);
    document.body.appendChild(modal);
    field.focus();

    const event = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(event);
    expect(document.activeElement).toBe(field);
    expect(event.defaultPrevented).toBe(false);
    modal.remove();
  });

  it('dismisses the drawer (without a modal guard) before focusing search on Ctrl+K', () => {
    const onDismissDrawer = vi.fn();
    renderHeader({ drawerOpen: true, onDismissDrawer });
    const drawer = document.createElement('div');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('data-app-drawer', '');
    document.body.appendChild(drawer);

    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(onDismissDrawer).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(screen.getByRole('searchbox', { name: 'Search observables' }));
    drawer.remove();
  });
});

describe('Header mobile search overlay', () => {
  it('takes the covered header controls out of the tab order while open', () => {
    setWide(false);
    renderHeader();
    const menu = screen.getByRole('button', { name: 'Toggle navigation' });
    const searchButton = screen.getByRole('button', { name: 'Search' });
    fireEvent.click(searchButton);

    for (const el of [menu, searchButton, screen.getByText('EmergentCTI').closest('a')!]) {
      expect(el.hasAttribute('inert')).toBe(true);
      expect(el.getAttribute('aria-hidden')).toBe('true');
      expect(el.getAttribute('tabindex')).toBe('-1');
    }

    // Escape closes the overlay and returns focus to the (now visible) button.
    fireEvent.keyDown(screen.getByRole('searchbox', { name: 'Search observables' }), { key: 'Escape' });
    expect(screen.queryByRole('button', { name: 'Close search' })).toBeNull();
    expect(menu.hasAttribute('inert')).toBe(false);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Search' }));
  });

  it('on md+ Ctrl+K does not open the mobile overlay and Escape just blurs the field', () => {
    setWide(true);
    renderHeader();
    const input = screen.getByRole('searchbox', { name: 'Search observables' });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(document.activeElement).toBe(input);
    // No overlay state: nothing covered, no mobile close button.
    expect(screen.queryByRole('button', { name: 'Close search' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Toggle navigation' }).hasAttribute('inert')).toBe(false);

    fireEvent.keyDown(input, { key: 'Escape' });
    expect(document.activeElement).not.toBe(input);
    expect(document.activeElement).not.toBe(screen.getByRole('button', { name: 'Search' }));
  });
});
