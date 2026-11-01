// frontend/src/components/ui/Tabs.test.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
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
    function Stateful() {
      const [active, setActive] = useState('sources');
      return (
        <Tabs
          tabs={tabs}
          active={active}
          onChange={(k) => {
            onChange(k);
            setActive(k);
          }}
        />
      );
    }
    render(<Stateful />);
    const tab = (name: string) => screen.getByRole('tab', { name });
    const press = (key: string) => fireEvent.keyDown(document.activeElement as Element, { key });

    tab('Sources').focus();
    press('ArrowRight');
    expect(document.activeElement).toBe(tab('Raw JSON'));
    expect(tab('Raw JSON').getAttribute('aria-selected')).toBe('true');
    expect(tab('Raw JSON').tabIndex).toBe(0);

    press('ArrowRight');
    expect(document.activeElement).toBe(tab('History'));

    press('ArrowRight'); // wraps
    expect(document.activeElement).toBe(tab('Sources'));

    press('ArrowLeft'); // wraps back
    expect(document.activeElement).toBe(tab('History'));
    expect(onChange).toHaveBeenLastCalledWith('history');

    press('Home');
    expect(document.activeElement).toBe(tab('Sources'));
    expect(tab('Sources').getAttribute('aria-selected')).toBe('true');

    press('End');
    expect(document.activeElement).toBe(tab('History'));
    expect(onChange).toHaveBeenLastCalledWith('history');

    onChange.mockClear();
    press('End'); // already selected
    expect(onChange).not.toHaveBeenCalled();
  });
});
