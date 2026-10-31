import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { Header } from './Header';

afterEach(cleanup);

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
});
