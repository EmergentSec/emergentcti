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
  'ip-addr': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'domain-name': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  'url': 'bg-green-500/20 text-green-400 border-green-500/30',
  'file-hash': 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  'email-addr': 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  'command-line': 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
}

export const typeLabels: Record<string, string> = {
  'ip-addr': 'IP Address',
  'domain-name': 'Domain',
  'url': 'URL',
  'file-hash': 'File Hash',
  'email-addr': 'Email',
  'command-line': 'Command Line',
}

export function confidenceColor(score: number): string {
  if (score >= 80) return 'text-red-400'
  if (score >= 60) return 'text-orange-400'
  if (score >= 40) return 'text-yellow-400'
  return 'text-gray-400'
}
