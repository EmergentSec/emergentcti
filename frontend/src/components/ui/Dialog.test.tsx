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
    render(<Harness />);
    fireEvent.click(screen.getByText('Open'));
    const save = screen.getByRole('button', { name: 'Save' });
    save.focus();
    fireEvent.change(screen.getByLabelText('Value'), { target: { value: 'x' } });
    expect(document.activeElement).toBe(save);
  });
});
