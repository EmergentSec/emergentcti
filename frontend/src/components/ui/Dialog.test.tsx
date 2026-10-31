import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Dialog } from './Dialog';

afterEach(cleanup);

function Harness({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Open</button>
      <Dialog
        open={open}
        onClose={() => { onClose?.(); setOpen(false); }}
        title="Add allowlist entry"
      >
        <input aria-label="Value" />
        <button>Save</button>
      </Dialog>
    </>
  );
}

describe('Dialog', () => {
  it('is a labelled modal dialog with an accessible close button', () => {
    render(<Harness />);
    fireEvent.click(screen.getByText('Open'));
    const dialog = screen.getByRole('dialog', { name: 'Add allowlist entry' });
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(screen.getByRole('button', { name: 'Close' })).toBeTruthy();
  });

  it('focuses the first field on open and restores focus on close', () => {
    render(<Harness />);
    const opener = screen.getByText('Open');
    opener.focus();
    fireEvent.click(opener);
    expect(document.activeElement).toBe(screen.getByLabelText('Value'));

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    fireEvent.click(screen.getByText('Open'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('does not steal focus back when the parent re-renders', () => {
    // Controlled field: every keystroke re-renders the parent, which passes a
    // fresh inline onClose to Dialog each time.
    let renders = 0;
    function ControlledHarness() {
      const [value, setValue] = useState('');
      renders += 1;
      return (
        <Dialog open onClose={() => setValue('')} title="Edit">
          <input aria-label="Value" value={value} onChange={(e) => setValue(e.target.value)} />
          <button>Save</button>
        </Dialog>
      );
    }
    render(<ControlledHarness />);
    const input = screen.getByLabelText('Value') as HTMLInputElement;
    expect(document.activeElement).toBe(input);

    const save = screen.getByRole('button', { name: 'Save' });
    save.focus();
    const before = renders;
    fireEvent.change(input, { target: { value: 'x' } });
    expect(renders).toBeGreaterThan(before);
    expect(input.value).toBe('x');
    expect(document.activeElement).toBe(save);
  });
});
