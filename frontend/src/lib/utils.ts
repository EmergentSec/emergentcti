import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function formatRelativeTime(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export const typeColors: Record<string, string> = {
  'ip-addr': 'border-cat-blue/30 bg-cat-soft-blue text-cat-ink-blue',
  'domain-name': 'border-cat-purple/30 bg-cat-soft-purple text-cat-ink-purple',
  'url': 'border-cat-green/30 bg-cat-soft-green text-cat-ink-green',
  'file-hash': 'border-cat-orange/30 bg-cat-soft-orange text-cat-ink-orange',
  'email-addr': 'border-cat-pink/30 bg-cat-soft-pink text-cat-ink-pink',
  'command-line': 'border-cat-yellow/30 bg-cat-soft-yellow text-cat-ink-yellow',
}

export const typeLabels: Record<string, string> = {
  'ip-addr': 'IP Address',
  'domain-name': 'Domain',
  'url': 'URL',
  'file-hash': 'File Hash',
  'email-addr': 'Email',
  'command-line': 'Command Line',
}
