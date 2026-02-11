import {
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import { cn } from '@/lib/utils';

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      previousFocus.current = document.activeElement as HTMLElement;
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
      if (previousFocus.current) {
        previousFocus.current.focus();
      }
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  const handleKeyDown = useCallback(
    (e: ReactKeyboardEvent) => {
      if (e.key === 'Escape') {
        onOpenChange(false);
      }
    },
    [onOpenChange]
  );

  const handleOverlayClick = useCallback(
    (e: ReactMouseEvent) => {
      if (e.target === overlayRef.current) {
        onOpenChange(false);
      }
    },
    [onOpenChange]
  );

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
    >
      {children}
    </div>
  );
}

interface DialogContentProps {
  children: ReactNode;
  className?: string;
}

export function DialogContent({ children, className }: DialogContentProps) {
  return (
    <div
      className={cn(
        'relative w-full max-w-lg rounded-lg border bg-card p-6 shadow-lg',
        'animate-in fade-in-0 zoom-in-95',
        className
      )}
      role="document"
    >
      {children}
    </div>
  );
}

interface DialogHeaderProps {
  children: ReactNode;
  className?: string;
}

export function DialogHeader({ children, className }: DialogHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col space-y-1.5 text-center sm:text-left mb-4',
        className
      )}
    >
      {children}
    </div>
  );
}

interface DialogTitleProps {
  children: ReactNode;
  className?: string;
}

export function DialogTitle({ children, className }: DialogTitleProps) {
  return (
    <h2
      className={cn(
        'text-lg font-semibold leading-none tracking-tight',
        className
      )}
    >
      {children}
    </h2>
  );
}

interface DialogDescriptionProps {
  children: ReactNode;
  className?: string;
}

export function DialogDescription({
  children,
  className,
}: DialogDescriptionProps) {
  return (
    <p className={cn('text-sm text-muted-foreground', className)}>{children}</p>
  );
}

interface DialogFooterProps {
  children: ReactNode;
  className?: string;
}

export function DialogFooter({ children, className }: DialogFooterProps) {
  return (
    <div
      className={cn(
        'flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-4',
        className
      )}
    >
      {children}
    </div>
  );
}

interface DialogCloseProps {
  onClose: () => void;
  className?: string;
}

export function DialogClose({ onClose, className }: DialogCloseProps) {
  return (
    <button
      className={cn(
        'absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100',
        'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        className
      )}
      onClick={onClose}
      aria-label="Close"
    >
      <span className="text-lg leading-none">&times;</span>
    </button>
  );
}
