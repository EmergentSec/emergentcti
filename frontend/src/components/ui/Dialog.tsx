import { type ReactNode, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}

export function Dialog({ open, onClose, title, children, className }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/60" onClick={onClose} />

      {/* Content */}
      <div
        className={cn(
          'relative z-50 w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-lg',
          'animate-in fade-in-0 zoom-in-95',
          className,
        )}
      >
        {/* Header */}
        {title && (
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
            <button
              onClick={onClose}
              className="rounded-sm p-1 text-muted-foreground hover:text-foreground transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 4l8 8M12 4l-8 8" />
              </svg>
            </button>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body,
  );
}
