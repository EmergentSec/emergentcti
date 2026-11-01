import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import type { ContentFormat } from '@/types/report'
import { cn } from '@/lib/utils'

const markdownComponents: Components = {
  a: ({ href, children, ...props }) => {
    let safeHref: string | undefined
    if (href) {
      try {
        const parsed = new URL(href, 'https://example.invalid')
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
          safeHref = href
        }
      } catch {
        safeHref = undefined
      }
    }
    return (
      <a
        href={safeHref}
        target="_blank"
        rel="noopener noreferrer nofollow"
        className="text-primary underline-offset-2 hover:underline"
        {...props}
      >
        {children}
      </a>
    )
  },
  img: ({ alt }) => (
    <span className="text-sm italic text-muted-foreground">{alt?.trim() || 'Image'}</span>
  ),
}

interface ReportContentProps {
  content: string | null
  contentFormat: ContentFormat
  className?: string
}

export function ReportContent({ content, contentFormat, className }: ReportContentProps) {
  if (!content?.trim()) {
    return <p className={cn('text-sm text-muted-foreground', className)}>No content.</p>
  }

  if (contentFormat === 'text') {
    return (
      <pre
        className={cn(
          'whitespace-pre-wrap break-words rounded-lg border border-border bg-surface2 p-4 font-mono text-sm text-foreground',
          className,
        )}
      >
        {content}
      </pre>
    )
  }

  return (
    <div
      className={cn(
        'prose prose-sm max-w-none text-foreground dark:prose-invert',
        '[&_pre]:overflow-x-auto [&_code]:rounded [&_code]:bg-surface2 [&_code]:px-1',
        className,
      )}
    >
      <ReactMarkdown skipHtml components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

export function isSafeHttpUrl(url: string | null | undefined): url is string {
  if (!url) return false
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function formatProvenance(value: string | null | undefined): string {
  return value?.trim() ? value : 'Unknown'
}
