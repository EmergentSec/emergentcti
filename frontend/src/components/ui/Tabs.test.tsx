// frontend/src/components/ui/Tabs.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Tabs } from './Tabs';

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
});
