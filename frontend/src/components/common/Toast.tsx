import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

export type ToastVariant = 'success' | 'error' | 'info';

export interface ToastData {
  id: string;
  message: string;
  variant: ToastVariant;
}

const variantStyles: Record<ToastVariant, string> = {
  success: 'border-emerald-500/50 bg-emerald-950/80 text-emerald-200',
  error: 'border-red-500/50 bg-red-950/80 text-red-200',
  info: 'border-blue-500/50 bg-blue-950/80 text-blue-200',
};

const variantIcons: Record<ToastVariant, JSX.Element> = {
  success: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3.5 8 6.5 11 12.5 5" />
    </svg>
  ),
  error: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="6" />
      <line x1="5.5" y1="5.5" x2="10.5" y2="10.5" />
      <line x1="10.5" y1="5.5" x2="5.5" y2="10.5" />
    </svg>
  ),
  info: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="6" />
      <line x1="8" y1="7" x2="8" y2="11" />
      <line x1="8" y1="5" x2="8" y2="5.5" />
    </svg>
  ),
};

interface ToastItemProps {
  toast: ToastData;
  onDismiss: (id: string) => void;
}

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Trigger slide-in animation
    requestAnimationFrame(() => setVisible(true));

    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(toast.id), 200);
    }, 4000);

    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-md border px-4 py-3 text-sm shadow-lg transition-all duration-200',
        variantStyles[toast.variant],
        visible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0',
      )}
    >
      {variantIcons[toast.variant]}
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={() => {
          setVisible(false);
          setTimeout(() => onDismiss(toast.id), 200);
        }}
        className="ml-2 shrink-0 rounded p-0.5 hover:bg-white/10 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3l8 8M11 3l-8 8" />
        </svg>
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: ToastData[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
