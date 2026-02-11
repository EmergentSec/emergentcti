import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date));
}

export function formatRelativeTime(date: string | Date): string {
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 30) return `${diffDay}d ago`;
  return formatDate(date);
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}

export const OBSERVABLE_TYPE_COLORS: Record<string, string> = {
  'ip-addr': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  'domain-name': 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  'url': 'bg-green-500/20 text-green-400 border-green-500/30',
  'file-hash': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  'email-addr': 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  'command-line': 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  'user-agent': 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  'certificate': 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  'asn': 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  'cidr': 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

export const OBSERVABLE_TYPE_DOT_COLORS: Record<string, string> = {
  'ip-addr': 'bg-purple-400',
  'domain-name': 'bg-cyan-400',
  'url': 'bg-green-400',
  'file-hash': 'bg-amber-400',
  'email-addr': 'bg-pink-400',
  'command-line': 'bg-gray-400',
  'user-agent': 'bg-gray-400',
  'certificate': 'bg-gray-400',
  'asn': 'bg-gray-400',
  'cidr': 'bg-gray-400',
};

export const OBSERVABLE_TYPE_LABELS: Record<string, string> = {
  'ip-addr': 'IP Address',
  'domain-name': 'Domain',
  'url': 'URL',
  'file-hash': 'File Hash',
  'email-addr': 'Email',
  'command-line': 'Command Line',
  'user-agent': 'User Agent',
  'certificate': 'Certificate',
  'asn': 'ASN',
  'cidr': 'CIDR',
};

export const TLP_COLORS: Record<string, string> = {
  clear: 'bg-white/20 text-white border-white/30',
  green: 'bg-green-500/20 text-green-400 border-green-500/30',
  amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  'amber+strict': 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  red: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export const FEED_TYPE_LABELS: Record<string, string> = {
  api: 'API',
  taxii: 'TAXII',
  file: 'File',
  scraper: 'Scraper',
};
