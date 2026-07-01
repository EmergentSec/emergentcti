import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { DecayChart, projectDecayScore } from './DecayChart'

afterEach(cleanup)

// ---------------------------------------------------------------------------
// Pure projection function — no DOM needed
// ---------------------------------------------------------------------------

describe('projectDecayScore', () => {
  const NATIVE = 45
  const DECAY_DAYS = 30
  const RATE = 5
  const FLOOR = 10

  it('returns nativeMax before the decay threshold', () => {
    expect(projectDecayScore(0, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(NATIVE)
    expect(projectDecayScore(15, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(NATIVE)
    expect(projectDecayScore(30, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(NATIVE)
  })

  it('drops by 1× rate immediately after threshold (first partial week counts as 1)', () => {
    // d=31: floor((31-30)/7)=0 → max(1,0)=1 → 45 − 1×5 = 40
    expect(projectDecayScore(31, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(40)
    // d=36: floor(6/7)=0 → max(1,0)=1 → 40
    expect(projectDecayScore(36, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(40)
  })

  it('drops by 2× rate after one full week past threshold', () => {
    // d=37: floor(7/7)=1 → max(1,1)=1 → still 40
    expect(projectDecayScore(37, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(40)
    // d=44: floor(14/7)=2 → max(1,2)=2 → 45 − 2×5 = 35
    expect(projectDecayScore(44, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(35)
  })

  it('floors at decayFloor and does not go below it', () => {
    // 7 weeks to deplete: (45−10)/5 = 7 → d = 30+49=79 reaches floor
    // d=79: floor(49/7)=7 → 45−7×5=10 (floor exactly)
    expect(projectDecayScore(79, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(10)
    // d=200: would be deeply negative without floor
    expect(projectDecayScore(200, NATIVE, DECAY_DAYS, RATE, FLOOR)).toBe(10)
  })
})

// ---------------------------------------------------------------------------
// Component rendering — text only (recharts SVG doesn't lay out in happy-dom)
// ---------------------------------------------------------------------------

describe('DecayChart', () => {
  const PROPS = {
    nativeMax: 45,
    ageDays: 45,
    decayDays: 30,
    decayRate: 5,
    decayFloor: 10,
  }

  it('renders the "Confidence decay" title', () => {
    render(<DecayChart {...PROPS} />)
    expect(screen.getByText('Confidence decay')).toBeTruthy()
  })

  it('renders the subtitle', () => {
    render(<DecayChart {...PROPS} />)
    expect(
      screen.getByText(/Score decays from native as the indicator ages without re-sighting/),
    ).toBeTruthy()
  })

  it('shows a linear decay caption (−rate/wk after Xd format)', () => {
    render(<DecayChart {...PROPS} />)
    expect(screen.getByTestId('decay-caption').textContent).toBe('−5/wk after 30d')
  })

  it('does NOT mention half-life anywhere', () => {
    render(<DecayChart {...PROPS} />)
    expect(screen.queryByText(/half.life/i)).toBeNull()
    expect(screen.queryByText(/halflife/i)).toBeNull()
  })

  it('renders different caption values when props change', () => {
    render(
      <DecayChart
        nativeMax={80}
        ageDays={10}
        decayDays={14}
        decayRate={3}
        decayFloor={20}
      />,
    )
    expect(screen.getByTestId('decay-caption').textContent).toBe('−3/wk after 14d')
  })
})
