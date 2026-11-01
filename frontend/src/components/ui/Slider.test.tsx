// frontend/src/components/ui/Slider.test.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Slider } from './Slider';

afterEach(cleanup);

describe('Slider', () => {
  it('emits the numeric value on change', () => {
    const onChange = vi.fn();
    render(<Slider value={20} min={0} max={100} step={5} onChange={onChange} />);
    fireEvent.change(screen.getByRole('slider'), { target: { value: '40' } });
    expect(onChange).toHaveBeenCalledWith(40);
  });

  it('is a native range input without a redundant explicit role', () => {
    render(<Slider value={20} onChange={() => {}} />);
    const el = screen.getByRole('slider') as HTMLInputElement;
    expect(el.tagName).toBe('INPUT');
    expect(el.type).toBe('range');
    expect(el.hasAttribute('role')).toBe(false);
  });
});
