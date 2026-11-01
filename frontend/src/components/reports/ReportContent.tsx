import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import type { ContentFormat } from '@/types/report'
import { cn } from '@/lib/utils'

export const reportMarkdownComponents: Components = {
  h1: ({ node: _node, className, ...props }) => (
    <h1
      className={cn(
        'mb-4 mt-6 scroll-m-20 text-2xl font-bold tracking-tight text-foreground first:mt-0',
        className,
      )}
      {...props}
    />
  ),
  h2: ({ node: _node, className, ...props }) => (
    <h2
      className={cn(
        'mb-3 mt-5 scroll-m-20 text-xl font-semibold tracking-tight text-foreground first:mt-0',
        className,
      )}
      {...props}
    />
  ),
  h3: ({ node: _node, className, ...props }) => (
    <h3
      className={cn(
        'mb-2 mt-4 scroll-m-20 text-lg font-semibold tracking-tight text-foreground first:mt-0',
        className,
      )}
      {...props}
    />
  ),
  h4: ({ node: _node, className, ...props }) => (
    <h4
      className={cn(
        'mb-2 mt-3 scroll-m-20 text-base font-semibold text-foreground first:mt-0',
        className,
      )}
      {...props}
    />
  ),
  p: ({ node: _node, className, ...props }) => (
    <p className={cn('mb-4 leading-relaxed last:mb-0', className)} {...props} />
  ),
  ul: ({ node: _node, className, ...props }) => (
    <ul className={cn('mb-4 list-disc space-y-1 pl-6 last:mb-0', className)} {...props} />
  ),
  ol: ({ node: _node, className, ...props }) => (
    <ol className={cn('mb-4 list-decimal space-y-1 pl-6 last:mb-0', className)} {...props} />
  ),
  li: ({ node: _node, className, ...props }) => (
    <li className={cn('leading-relaxed', className)} {...props} />
  ),
  blockquote: ({ node: _node, className, ...props }) => (
    <blockquote
      className={cn(
        'mb-4 border-l-4 border-border pl-4 italic text-muted-foreground last:mb-0',
        className,
      )}
      {...props}
    />
  ),
  hr: ({ node: _node, className, ...props }) => (
    <hr className={cn('my-6 border-border', className)} {...props} />
  ),
  table: ({ node: _node, className, ...props }) => (
    <div className="mb-4 overflow-x-auto last:mb-0">
      <table className={cn('w-full border-collapse text-sm', className)} {...props} />
    </div>
  ),
  thead: ({ node: _node, className, ...props }) => (
    <thead className={cn(className)} {...props} />
  ),
  tbody: ({ node: _node, className, ...props }) => (
    <tbody className={cn(className)} {...props} />
  ),
  tr: ({ node: _node, className, ...props }) => (
    <tr className={cn('border-b border-border', className)} {...props} />
  ),
  th: ({ node: _node, className, ...props }) => (
    <th
      className={cn(
        'border border-border bg-surface2 px-3 py-2 text-left font-semibold text-foreground',
        className,
      )}
      {...props}
    />
  ),
  td: ({ node: _node, className, ...props }) => (
    <td className={cn('border border-border px-3 py-2 text-foreground', className)} {...props} />
  ),
  code: ({ node: _node, className, children, ...props }) => {
    const isBlock = /language-/.test(className ?? '')
    if (isBlock) {
      return (
        <code className={cn('font-mono text-sm text-foreground', className)} {...props}>
          {children}
        </code>
      )
    }
    return (
      <code
        className={cn(
          'rounded bg-surface2 px-1 py-0.5 font-mono text-[0.875em] text-foreground',
          className,
        )}
        {...props}
      >
        {children}
      </code>
    )
  },
  pre: ({ node: _node, className, ...props }) => (
    <pre
      className={cn(
        'mb-4 overflow-x-auto rounded-lg border border-border bg-surface2 p-4 font-mono text-sm text-foreground last:mb-0',
        className,
      )}
      {...props}
    />
  ),
  a: ({ href, children, node: _node, className, ...props }) => {
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
        {...props}
        href={safeHref}
        target="_blank"
        rel="noopener noreferrer nofollow"
        className={cn('text-primary underline-offset-2 hover:underline', className)}
      >
        {children}
      </a>
    )
  },
  img: ({ node: _node, alt }) => (
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
    <div className={cn('max-w-none text-sm text-foreground', className)}>
      <ReactMarkdown skipHtml components={reportMarkdownComponents}>
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
