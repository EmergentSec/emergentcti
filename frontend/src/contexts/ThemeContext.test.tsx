// frontend/src/contexts/ThemeContext.test.tsx
import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeContext';

function Probe() {
  const { theme, toggle } = useTheme();
  return <button onClick={toggle}>theme:{theme}</button>;
}

describe('ThemeContext', () => {
  beforeEach(() => localStorage.clear());

  it('defaults to dark and toggles to light, updating the html class', () => {
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByText('theme:dark')).toBeTruthy();
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    act(() => screen.getByRole('button').click());
    expect(screen.getByText('theme:light')).toBeTruthy();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('light');
  });
});
