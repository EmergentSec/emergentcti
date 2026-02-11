import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface Toast {
  id: string;
  message: string;
  variant: 'success' | 'error' | 'info';
}

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

const VARIANT_STYLES: Record<string, string> = {
  success: 'border-l-4 border-l-green-500',
  error: 'border-l-4 border-l-red-500',
  info: 'border-l-4 border-l-blue-500',
};

const VARIANT_ICONS: Record<string, string> = {
  success: '\u2713',
  error: '\u2717',
  info: '\u2139',
};

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Trigger fade-in on mount
    const frame = requestAnimationFrame(() => {
      setVisible(true);
    });
    return () => cancelAnimationFrame(frame);
  }, []);

  const handleDismiss = () => {
    setVisible(false);
    // Wait for transition to finish before removing
    setTimeout(() => onDismiss(toast.id), 150);
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex items-center gap-3 rounded-md bg-card px-4 py-3 shadow-lg ring-1 ring-border',
        'transition-all duration-150 ease-out',
        visible
          ? 'translate-y-0 opacity-100'
          : 'translate-y-2 opacity-0',
        VARIANT_STYLES[toast.variant]
      )}
    >
      <span className="text-sm font-medium shrink-0">
        {VARIANT_ICONS[toast.variant]}
      </span>
      <p className="flex-1 text-sm text-foreground">{toast.message}</p>
      <button
        onClick={handleDismiss}
        className="shrink-0 text-muted-foreground hover:text-foreground transition-colors p-0.5"
        aria-label="Dismiss notification"
      >
        {'\u2715'}
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
