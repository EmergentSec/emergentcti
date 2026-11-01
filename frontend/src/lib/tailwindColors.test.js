import postcss from 'postcss'
import tailwindcss from 'tailwindcss'
import { beforeAll, describe, expect, it } from 'vitest'
import tailwindConfig from '../../tailwind.config.js'

const candidates = [
  'bg-destructive',
  'bg-destructive/10',
  'border-cat-blue/30',
  'bg-destructive-soft',
]

let root

function declaration(selector, property) {
  let value
  root.walkRules(selector, (rule) => {
    rule.walkDecls(property, (decl) => {
      value = decl.value
    })
  })
  return value
}

beforeAll(async () => {
  const config = {
    ...tailwindConfig,
    content: [
      ...tailwindConfig.content,
      { raw: `<div class="${candidates.join(' ')}"></div>`, extension: 'html' },
    ],
  }
  const result = await postcss([tailwindcss(config)]).process('@tailwind utilities;', {
    from: undefined,
  })
  root = result.root
})

describe('Tailwind theme color opacity modifiers', () => {
  it('keeps unmodified theme colors at full opacity', () => {
    expect(declaration('.bg-destructive', 'background-color')).toBe(
      'color-mix(in srgb, var(--destructive) calc(var(--tw-bg-opacity, 1) * 100%), transparent)',
    )
    expect(declaration('.bg-destructive-soft', 'background-color')).toContain(
      'var(--destructive-soft)',
    )
  })

  it('generates background and border opacity modifiers', () => {
    expect(declaration('.bg-destructive\\/10', 'background-color')).toContain(
      'var(--destructive) calc(0.1 * 100%)',
    )
    expect(declaration('.border-cat-blue\\/30', 'border-color')).toContain(
      'var(--cat-blue) calc(0.3 * 100%)',
    )
  })
})
