import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { ToastContainer, type ToastData, type ToastVariant } from '@/components/common/Toast'

type ToastType = ToastVariant

interface ToastContextType {
  toast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToast(): ToastContextType {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

let nextId = 0

/**
 * App-wide toasts. Rendering (tokens, polite live region, "Dismiss
 * notification" button, auto-dismiss timer) lives in common/Toast.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastData[]>([])

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = String(nextId++)
    setToasts((prev) => [...prev, { id, message, variant: type }])
  }, [])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}
