// frontend/src/components/ui/Tabs.test.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Tabs } from './Tabs';

afterEach(cleanup);

describe('Tabs', () => {
  it('marks the active tab and emits onChange', () => {
    const onChange = vi.fn();
    render(
      <Tabs
        tabs={[{ key: 'sources', label: 'Sources' }, { key: 'raw', label: 'Raw JSON' }]}
        active="sources"
        onChange={onChange}
      />,
    );
    expect(screen.getByRole('tab', { name: 'Sources' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(screen.getByRole('tab', { name: 'Raw JSON' }));
    expect(onChange).toHaveBeenCalledWith('raw');
  });

  it('does not emit onChange when the already-selected tab is clicked', () => {
    const onChange = vi.fn();
    render(
      <Tabs
        tabs={[{ key: 'sources', label: 'Sources' }, { key: 'raw', label: 'Raw JSON' }]}
        active="sources"
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole('tab', { name: 'Sources' }));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe('Tabs keyboard support', () => {
  const tabs = [
    { key: 'sources', label: 'Sources' },
    { key: 'raw', label: 'Raw JSON' },
    { key: 'history', label: 'History' },
  ];

  it('uses a roving tabindex on the selected tab', () => {
    render(<Tabs tabs={tabs} active="raw" onChange={() => {}} />);
    expect(screen.getByRole('tab', { name: 'Raw JSON' }).tabIndex).toBe(0);
    expect(screen.getByRole('tab', { name: 'Sources' }).tabIndex).toBe(-1);
  });

  it('moves focus and selects with Arrow keys, wrapping, and Home/End', () => {
    const onChange = vi.fn();
    render(<Tabs tabs={tabs} active="sources" onChange={onChange} />);
    const sources = screen.getByRole('tab', { name: 'Sources' });

    fireEvent.keyDown(sources, { key: 'ArrowRight' });
    expect(onChange).toHaveBeenLastCalledWith('raw');
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Raw JSON' }));

    fireEvent.keyDown(sources, { key: 'ArrowLeft' });
    expect(onChange).toHaveBeenLastCalledWith('history');

    fireEvent.keyDown(sources, { key: 'End' });
    expect(onChange).toHaveBeenLastCalledWith('history');

    onChange.mockClear();
    fireEvent.keyDown(sources, { key: 'Home' });
    expect(onChange).not.toHaveBeenCalled(); // already selected
    expect(document.activeElement).toBe(sources);
  });
});
