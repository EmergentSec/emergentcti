import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import { ToastContainer } from '@/components/common/Toast';

interface Toast {
  id: string;
  message: string;
  variant: 'success' | 'error' | 'info';
}

interface ToastContextValue {
  addToast: (message: string, variant?: 'success' | 'error' | 'info') => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let toastCounter = 0;

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (message: string, variant: 'success' | 'error' | 'info' = 'info') => {
      const id = `toast-${++toastCounter}`;
      const toast: Toast = { id, message, variant };

      setToasts((prev) => {
        const next = [...prev, toast];
        // Keep max 5 visible toasts
        if (next.length > 5) {
          return next.slice(next.length - 5);
        }
        return next;
      });

      // Auto-dismiss after 3 seconds
      setTimeout(() => {
        removeToast(id);
      }, 3000);
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
