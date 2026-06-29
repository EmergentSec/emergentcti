// frontend/src/components/ui/Slider.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Slider } from './Slider';

describe('Slider', () => {
  it('emits the numeric value on change', () => {
    const onChange = vi.fn();
    render(<Slider value={20} min={0} max={100} step={5} onChange={onChange} />);
    fireEvent.change(screen.getByRole('slider'), { target: { value: '40' } });
    expect(onChange).toHaveBeenCalledWith(40);
  });
});
