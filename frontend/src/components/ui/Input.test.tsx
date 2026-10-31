import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Input } from './Input';
import { Select } from './Select';

afterEach(cleanup);

describe('Input / Select error state', () => {
  it('links the error text with aria-invalid and aria-describedby', () => {
    render(<Input label="Feed URL" error="URL is required" aria-describedby="hint" />);
    const input = screen.getByLabelText('Feed URL');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    const ids = input.getAttribute('aria-describedby')!.split(' ');
    expect(ids).toContain('hint');
    const errorId = ids.find((id) => id !== 'hint')!;
    expect(document.getElementById(errorId)?.textContent).toBe('URL is required');
  });

  it('has no error attributes when valid', () => {
    render(<Input label="Name" />);
    const input = screen.getByLabelText('Name');
    expect(input.hasAttribute('aria-invalid')).toBe(false);
    expect(input.hasAttribute('aria-describedby')).toBe(false);
  });

  it('supports the same error contract on Select', () => {
    render(<Select label="Type" options={[{ value: 'ip', label: 'IP' }]} error="Pick one" />);
    const select = screen.getByLabelText('Type');
    expect(select.getAttribute('aria-invalid')).toBe('true');
    expect(document.getElementById(select.getAttribute('aria-describedby')!)?.textContent).toBe('Pick one');
  });
});
