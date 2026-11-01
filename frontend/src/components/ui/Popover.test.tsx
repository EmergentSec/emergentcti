// frontend/src/components/ui/Popover.test.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Popover } from './Popover';

afterEach(cleanup);

describe('Popover', () => {
  it('opens on trigger click and closes on click-away', () => {
    render(
      <Popover trigger={<button>Export</button>}>
        <div>panel-content</div>
      </Popover>,
    );
    expect(screen.queryByText('panel-content')).toBeNull();
    fireEvent.click(screen.getByText('Export'));
    expect(screen.getByText('panel-content')).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByText('panel-content')).toBeNull();
  });

  it('exposes aria-haspopup and aria-expanded on a native button trigger', () => {
    render(
      <Popover trigger={<button>Export</button>}>
        <div>panel-content</div>
      </Popover>,
    );
    const trigger = screen.getByRole('button', { name: 'Export' });
    expect(trigger.getAttribute('aria-haspopup')).toBe('true');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    // Native buttons already toggle on Enter/Space; no extra role/tabindex is added.
    expect(trigger.hasAttribute('tabindex')).toBe(false);
  });

  it('makes a non-interactive trigger focusable and toggles it with Enter and Space', () => {
    render(
      <Popover trigger={<div>Export</div>}>
        <div>panel-content</div>
      </Popover>,
    );
    const trigger = screen.getByRole('button', { name: 'Export' });
    expect(trigger.getAttribute('tabindex')).toBe('0');
    expect(trigger.getAttribute('aria-haspopup')).toBe('true');

    fireEvent.keyDown(trigger, { key: 'Enter' });
    expect(screen.getByText('panel-content')).toBeTruthy();
    expect(trigger.getAttribute('aria-expanded')).toBe('true');

    fireEvent.keyDown(trigger, { key: ' ' });
    expect(screen.queryByText('panel-content')).toBeNull();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('wraps a plain-text trigger in a button', () => {
    render(
      <Popover trigger="Export">
        <div>panel-content</div>
      </Popover>,
    );
    const trigger = screen.getByRole('button', { name: 'Export' });
    expect(trigger.tagName).toBe('BUTTON');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('closes on Escape and returns focus to the trigger', () => {
    render(
      <Popover trigger={<button>Export</button>}>
        <button>inside</button>
      </Popover>,
    );
    const trigger = screen.getByRole('button', { name: 'Export' });
    fireEvent.click(trigger);
    const inside = screen.getByRole('button', { name: 'inside' });
    inside.focus();
    expect(document.activeElement).toBe(inside);

    fireEvent.keyDown(inside, { key: 'Escape' });
    expect(screen.queryByText('inside')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
