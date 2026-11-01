import { type ReactNode, useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';
import { getFocusable, trapTab } from './focus';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}

/**
 * Modal dialog. On open, focus moves to the first focusable control in the
 * body (falling back to the close button, then the panel); Tab is trapped;
 * Esc or the overlay closes; focus returns to the opener on close.
 */
export function Dialog({ open, onClose, title, children, className }: DialogProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  // Callers often pass an inline onClose; keep it in a ref so focus effects
  // run only when `open` changes, not on every render.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const target = getFocusable(bodyRef.current)[0] ?? getFocusable(panel)[0] ?? panel;
    target?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCloseRef.current();
      } else {
        trapTab(e, panelRef.current);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (opener && document.contains(opener)) opener.focus();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-overlay backdrop-blur-[2px]"
        aria-hidden="true"
        onClick={() => onCloseRef.current()}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        className={cn(
          'relative z-50 max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-popover p-6 text-foreground shadow-2xl',
          'focus:outline-none',
          className,
        )}
      >
        {title && (
          <div className="mb-4 flex items-start justify-between gap-4">
            <h2 id={titleId} className="text-lg font-semibold leading-tight text-foreground">
              {title}
            </h2>
            <button
              type="button"
              aria-label="Close"
              onClick={() => onCloseRef.current()}
              className="-mr-1.5 -mt-1 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-hover hover:text-foreground"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        )}
        <div ref={bodyRef}>{children}</div>
      </div>
    </div>,
    document.body,
  );
}
