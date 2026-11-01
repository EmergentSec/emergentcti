import postcss from 'postcss'
import tailwindcss from 'tailwindcss'
import { beforeAll, describe, expect, it } from 'vitest'
import tailwindConfig from '../../tailwind.config.js'

function colorNames(colors, path = []) {
  return Object.entries(colors).flatMap(([name, value]) => {
    if (path.length === 0 && name === 'cat-soft') return []

    const nextPath = name === 'DEFAULT' ? path : [...path, name]
    if (value && typeof value === 'object') return colorNames(value, nextPath)
    return [nextPath.join('-')]
  })
}

const opacityCandidates = colorNames(tailwindConfig.theme.extend.colors).map(
  (name) => `bg-${name}/50`,
)
const candidates = [
  ...opacityCandidates,
  'bg-destructive-soft',
  'border-destructive',
]

let root

function hasRule(candidate) {
  let found = false
  root.walkRules(`.${candidate.replaceAll('/', '\\/')}`, () => {
    found = true
  })
  return found
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
  it.each(opacityCandidates)('generates a rule for %s', (candidate) => {
    expect(hasRule(candidate)).toBe(true)
  })

  it('generates the destructive background and border rules', () => {
    expect(hasRule('bg-destructive-soft')).toBe(true)
    expect(hasRule('border-destructive')).toBe(true)
  })
})
