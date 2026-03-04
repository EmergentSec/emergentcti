import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: number
  message: string
  type: ToastType
}

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

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => dismiss(t.id)}
            className={cn(
              'px-4 py-3 rounded-lg shadow-lg border cursor-pointer transition-all',
              'animate-in slide-in-from-right-5 fade-in duration-300',
              t.type === 'success' && 'bg-green-900/90 border-green-700 text-green-100',
              t.type === 'error' && 'bg-red-900/90 border-red-700 text-red-100',
              t.type === 'info' && 'bg-card border-border text-foreground',
            )}
          >
            <div className="flex items-center gap-2">
              {t.type === 'success' && <span className="text-green-400">&#10003;</span>}
              {t.type === 'error' && <span className="text-red-400">&#10007;</span>}
              {t.type === 'info' && <span className="text-blue-400">&#9432;</span>}
              <span className="text-sm">{t.message}</span>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
