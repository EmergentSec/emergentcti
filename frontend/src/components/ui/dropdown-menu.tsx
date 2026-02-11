import {
  useRef,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { cn } from '@/lib/utils';

interface DropdownMenuProps {
  children: ReactNode;
}

export function DropdownMenu({ children }: DropdownMenuProps) {
  return <div className="relative inline-block text-left">{children}</div>;
}

interface DropdownMenuTriggerProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

export function DropdownMenuTrigger({
  children,
  className,
  onClick,
}: DropdownMenuTriggerProps) {
  return (
    <div className={cn('cursor-pointer', className)} onClick={onClick}>
      {children}
    </div>
  );
}

interface DropdownMenuContentProps {
  children: ReactNode;
  open: boolean;
  onClose: () => void;
  align?: 'start' | 'end';
  className?: string;
}

export function DropdownMenuContent({
  children,
  open,
  onClose,
  align = 'end',
  className,
}: DropdownMenuContentProps) {
  const ref = useRef<HTMLDivElement>(null);

  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        onClose();
      }
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
      return () =>
        document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [open, handleClickOutside]);

  if (!open) return null;

  return (
    <div
      ref={ref}
      className={cn(
        'absolute z-50 mt-2 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md',
        align === 'end' ? 'right-0' : 'left-0',
        className
      )}
      role="menu"
    >
      {children}
    </div>
  );
}

interface DropdownMenuItemProps {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
  destructive?: boolean;
}

export function DropdownMenuItem({
  children,
  onClick,
  className,
  destructive,
}: DropdownMenuItemProps) {
  return (
    <button
      className={cn(
        'relative flex w-full cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
        'transition-colors hover:bg-accent hover:text-accent-foreground',
        'focus:bg-accent focus:text-accent-foreground',
        destructive && 'text-red-400 hover:text-red-300',
        className
      )}
      role="menuitem"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

interface DropdownMenuSeparatorProps {
  className?: string;
}

export function DropdownMenuSeparator({
  className,
}: DropdownMenuSeparatorProps) {
  return <div className={cn('-mx-1 my-1 h-px bg-border', className)} />;
}

interface DropdownMenuLabelProps {
  children: ReactNode;
  className?: string;
}

export function DropdownMenuLabel({
  children,
  className,
}: DropdownMenuLabelProps) {
  return (
    <div className={cn('px-2 py-1.5 text-sm font-semibold', className)}>
      {children}
    </div>
  );
}
