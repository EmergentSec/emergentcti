import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppearanceSelector } from './AppearanceSelector';

const theme = vi.hoisted(() => ({
  preference: 'system' as 'system' | 'light' | 'dark',
  resolvedTheme: 'dark' as 'light' | 'dark',
  setPreference: vi.fn(),
}));
vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => theme }));

afterEach(cleanup);
beforeEach(() => {
  theme.preference = 'system';
  theme.resolvedTheme = 'dark';
  theme.setPreference.mockReset();
});

const radio = (name: string) => screen.getByRole('radio', { name });

describe('AppearanceSelector', () => {
  it('renders a labelled radio group with System, Light and Dark', () => {
    render(<AppearanceSelector />);
    const group = screen.getByRole('radiogroup', { name: 'Appearance' });
    expect(group).toBeTruthy();
    expect(screen.getAllByRole('radio').map((r) => r.textContent)).toEqual(['System', 'Light', 'Dark']);
  });

  it('keeps System checked in System mode even when it resolves to dark', () => {
    render(<AppearanceSelector />);
    expect(radio('System').getAttribute('aria-checked')).toBe('true');
    expect(radio('Dark').getAttribute('aria-checked')).toBe('false');
    expect(radio('Light').getAttribute('aria-checked')).toBe('false');
  });

  it('reflects an explicit preference and uses a roving tabindex', () => {
    theme.preference = 'light';
    theme.resolvedTheme = 'light';
    render(<AppearanceSelector />);
    expect(radio('Light').getAttribute('aria-checked')).toBe('true');
    expect(radio('Light').tabIndex).toBe(0);
    expect(radio('System').tabIndex).toBe(-1);
    expect(radio('Dark').tabIndex).toBe(-1);
  });

  it('calls setPreference on click', () => {
    render(<AppearanceSelector />);
    fireEvent.click(radio('Dark'));
    expect(theme.setPreference).toHaveBeenCalledWith('dark');
  });

  it('moves focus and selects with arrow keys, wrapping, plus Home/End', () => {
    render(<AppearanceSelector />);
    const system = radio('System');

    fireEvent.keyDown(system, { key: 'ArrowRight' });
    expect(theme.setPreference).toHaveBeenLastCalledWith('light');
    expect(document.activeElement).toBe(radio('Light'));

    fireEvent.keyDown(radio('Light'), { key: 'ArrowDown' });
    expect(theme.setPreference).toHaveBeenLastCalledWith('dark');

    fireEvent.keyDown(radio('Dark'), { key: 'ArrowRight' });
    expect(theme.setPreference).toHaveBeenLastCalledWith('system');

    fireEvent.keyDown(system, { key: 'ArrowLeft' });
    expect(theme.setPreference).toHaveBeenLastCalledWith('dark');
    expect(document.activeElement).toBe(radio('Dark'));

    fireEvent.keyDown(radio('Dark'), { key: 'ArrowUp' });
    expect(theme.setPreference).toHaveBeenLastCalledWith('light');

    fireEvent.keyDown(radio('Light'), { key: 'Home' });
    expect(theme.setPreference).toHaveBeenLastCalledWith('system');

    fireEvent.keyDown(system, { key: 'End' });
    expect(theme.setPreference).toHaveBeenLastCalledWith('dark');
  });
});
