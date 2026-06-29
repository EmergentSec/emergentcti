// frontend/src/components/ui/Slider.tsx
import { cn } from '@/lib/utils';

export interface SliderProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
  className?: string;
}

export function Slider({ value, min = 0, max = 100, step = 1, onChange, className }: SliderProps) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <input
      type="range"
      role="slider"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className={cn('h-1.5 w-full cursor-pointer appearance-none rounded-full', className)}
      style={{ background: `linear-gradient(to right, var(--brand) ${pct}%, var(--surface-3) ${pct}%)` }}
    />
  );
}
