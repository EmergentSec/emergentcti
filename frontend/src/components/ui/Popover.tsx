// frontend/src/components/ui/Popover.tsx
import {
  cloneElement,
  isValidElement,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react';
import { cn } from '@/lib/utils';

export interface PopoverProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: 'start' | 'end';
  className?: string;
}

// Host elements that are already focusable and fire click on Enter/Space.
const NATIVE_INTERACTIVE = new Set(['button', 'a', 'input', 'select', 'textarea', 'summary']);

export function Popover({ trigger, children, align = 'start', className }: PopoverProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setOpen(false);
      triggerRef.current?.querySelector<HTMLElement>('[aria-haspopup]')?.focus();
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const ariaProps = { 'aria-haspopup': 'true' as const, 'aria-expanded': open };

  let triggerNode: ReactNode;
  if (isValidElement<Record<string, unknown>>(trigger)) {
    // Components (e.g. <Button>) are assumed to render a native control.
    const isNative = typeof trigger.type !== 'string' || NATIVE_INTERACTIVE.has(trigger.type);
    triggerNode = cloneElement(
      trigger,
      isNative
        ? ariaProps
        : {
            ...ariaProps,
            role: 'button',
            tabIndex: 0,
            onKeyDown: (e: KeyboardEvent) => {
              if (e.key !== 'Enter' && e.key !== ' ') return;
              e.preventDefault();
              setOpen((o) => !o);
            },
          },
    );
  } else {
    triggerNode = (
      <button type="button" {...ariaProps}>
        {trigger}
      </button>
    );
  }

  return (
    <div ref={ref} className="relative inline-block">
      <div ref={triggerRef} onClick={() => setOpen((o) => !o)}>
        {triggerNode}
      </div>
      {open && (
        <div
          className={cn(
            'absolute z-50 mt-2 min-w-[14rem] rounded-md border border-border bg-popover p-1 shadow-lg',
            align === 'end' ? 'right-0' : 'left-0',
            className,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
