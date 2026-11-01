import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { ReportContent, reportMarkdownComponents } from './ReportContent'

afterEach(cleanup)

describe('ReportContent', () => {
  it('renders markdown headings and emphasis', () => {
    const { container } = render(
      <ReportContent
        content={'# Title\n\n**bold** and [link](https://example.com)'}
        contentFormat="markdown"
      />,
    )
    expect(within(container).getByRole('heading', { level: 1 }).textContent).toContain('Title')
    expect(screen.getByText('bold')).toBeTruthy()
    const link = screen.getByRole('link', { name: 'link' })
    expect(link.getAttribute('href')).toBe('https://example.com')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer nofollow')
  })

  it('does not emit script tags or execute raw HTML', () => {
    const { container } = render(
      <ReportContent
        content={'<script>alert(1)</script>\n\n![pic](https://example.com/x.png)'}
        contentFormat="markdown"
      />,
    )
    expect(container.querySelector('script')).toBeNull()
    expect(screen.getByText('pic')).toBeTruthy()
    expect(container.querySelector('img')).toBeNull()
  })

  it('blocks javascript: links in markdown', () => {
    const { container } = render(
      <ReportContent content="[click me](javascript:alert(1))" contentFormat="markdown" />,
    )
    const anchor = container.querySelector('a')
    expect(anchor?.textContent).toBe('click me')
    expect(anchor?.getAttribute('href')).toBeNull()
  })

  it('renders plain text in a pre block', () => {
    render(<ReportContent content={'line one\nline two'} contentFormat="text" />)
    const pre = screen.getByText(/line one/)
    expect(pre.tagName).toBe('PRE')
  })

  it('markdown links keep rel/target and omit node even with conflicting props', () => {
    const Link = reportMarkdownComponents.a!
    const { container } = render(
      <Link
        href="https://example.com"
        node={{ type: 'element', tagName: 'a', properties: {}, children: [] }}
        target="_self"
        rel="noopener"
      >
        link
      </Link>,
    )
    const anchor = container.querySelector('a')!
    expect(anchor.getAttribute('href')).toBe('https://example.com')
    expect(anchor.getAttribute('target')).toBe('_blank')
    expect(anchor.getAttribute('rel')).toBe('noopener noreferrer nofollow')
    expect(anchor.hasAttribute('node')).toBe(false)
  })
})
